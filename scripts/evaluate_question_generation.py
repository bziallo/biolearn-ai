"""Repeatable AI question-generation stability evaluation (isolated DB).

Usage:
    python scripts/evaluate_question_generation.py            # plan + estimate only
    python scripts/evaluate_question_generation.py --live     # real model calls

The script never reads or writes the real database/uploads. It creates a
temporary SQLite database with synthetic approved knowledge points, runs
several independent generation jobs, and reports target/saved/skipped/failed,
repair counts, model calls, tokens, latency and an estimated cost.

Pricing basis is printed with the result. DeepSeek's listed off-peak rates are
used only for an estimate; the provider's usage totals are the source of truth
for tokens.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.enums import QuestionType  # noqa: E402
from app.db.base import Base, utc_now  # noqa: E402
from app.db.session import build_engine  # noqa: E402
from app.models import Chapter, Document, KnowledgePoint, Question, Subject  # noqa: E402
from app.services import question_generation  # noqa: E402
from app.services.ai_config import effective_ai_settings  # noqa: E402

# USD per 1M tokens, DeepSeek listed off-peak, cache-miss input / output.
INPUT_USD_PER_M = 0.15
OUTPUT_USD_PER_M = 0.60

SYNTHETIC_POINTS = [
    (
        "细胞膜的选择透过性",
        "细胞膜允许部分物质通过，同时限制其他物质自由扩散。",
        ["选择透过性", "膜转运"],
        "细胞膜具有选择透过性。",
    ),
    (
        "被动运输与主动运输",
        "被动运输不消耗 ATP，顺浓度梯度；主动运输消耗 ATP，可逆浓度梯度。",
        ["被动运输", "主动运输", "ATP"],
        "主动运输需要消耗 ATP。",
    ),
    (
        "酶促反应的影响因素",
        "温度、pH 和底物浓度会影响酶促反应速率，过高温度会使酶变性。",
        ["温度", "pH", "底物浓度"],
        "高温会使酶变性失活。",
    ),
    (
        "DNA 复制的基本特征",
        "DNA 复制是半保留复制，以亲代链为模板，需要引物和 DNA 聚合酶。",
        ["半保留复制", "模板", "DNA 聚合酶"],
        "DNA 复制是半保留复制。",
    ),
    (
        "蛋白质的四级结构",
        "四级结构由多个亚基通过非共价键组装而成，血红蛋白是典型例子。",
        ["亚基", "非共价键", "血红蛋白"],
        "血红蛋白具有四级结构。",
    ),
    (
        "动作电位的产生",
        "动作电位由钠离子内流引起去极化，随后钾离子外流复极化。",
        ["去极化", "钠离子", "复极化"],
        "动作电位的去极化与钠离子内流有关。",
    ),
]

# Four independent batches covering different type mixes and point subsets.
BATCH_PLAN = [
    ([0, 1], [QuestionType.SINGLE_CHOICE, QuestionType.TRUE_FALSE]),
    ([2, 3], [QuestionType.MULTIPLE_CHOICE, QuestionType.SINGLE_CHOICE]),
    ([4, 5], [QuestionType.TRUE_FALSE, QuestionType.SHORT_ANSWER]),
    ([0, 3, 5], [QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE]),
]


def seed(factory) -> tuple[str, list[str]]:
    with factory() as db:
        subject = Subject(name="阶段五稳定性合成学科", description="仅用于隔离评估")
        db.add(subject)
        db.flush()
        chapter = Chapter(subject_id=subject.id, name="阶段五合成章节", description="")
        db.add(chapter)
        db.flush()
        document = Document(
            subject_id=subject.id,
            chapter_id=chapter.id,
            name="阶段五合成讲义",
            content_title="阶段五合成内容",
            original_filename="phase5-synthetic.txt",
            storage_name="phase5-synthetic.txt",
            mime_type="text/plain",
            extension=".txt",
            size_bytes=200,
            sha256="f" * 64,
            status="parsed",
            page_count=1,
            parsed_at=utc_now(),
        )
        db.add(document)
        db.flush()
        point_ids: list[str] = []
        for index, (name, explanation, core, quote) in enumerate(SYNTHETIC_POINTS):
            point = KnowledgePoint(
                subject_id=subject.id,
                chapter_id=chapter.id,
                document_id=document.id,
                name=name,
                explanation=explanation,
                core_points=core,
                source_quote=quote,
                source_quote_verified=True,
                source_page=index + 1,
                source_locator=f"第 {index + 1} 页",
                review_status="approved",
                needs_review=False,
                origin="manual",
                published_at=utc_now(),
            )
            db.add(point)
            db.flush()
            point_ids.append(point.id)
        db.commit()
        return subject.id, point_ids


def run_batch(factory, subject_id: str, point_ids: list[str], types, count: int, settings):
    with factory() as db:
        job = question_generation.create_generation_job(
            db,
            subject_id=subject_id,
            knowledge_point_ids=point_ids,
            types=types,
            count=count,
            settings=settings,
        )
    started = time.perf_counter()
    question_generation.run_generation(
        job.id,
        session_factory=factory,
        settings=settings,
    )
    latency = round(time.perf_counter() - started, 2)
    with factory() as db:
        stored = question_generation.get_job_or_404(db, job.id)
        saved = db.query(Question).filter(Question.generation_job_id == job.id).count()
        timings = stored.timings or {}
        return {
            "job_id": job.id,
            "types": [item.value for item in types],
            "knowledge_point_count": len(point_ids),
            "target": count,
            "status": stored.status,
            "saved": saved,
            "skipped": stored.skipped_count,
            "error": stored.error,
            "error_kind": timings.get("error_kind"),
            "format_repairs": int(timings.get("format_repairs") or 0),
            "model_calls": int(timings.get("model_calls") or 0),
            "tokens": timings.get("tokens") or {},
            "latency_seconds": latency,
            "warnings": timings.get("warnings") or [],
            "json_mode_fallback": timings.get("json_mode_fallback"),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="actually call the model")
    parser.add_argument("--target", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--output", default=str(ROOT / "outputs" / "phase5_generation_eval.json"))
    args = parser.parse_args()

    batches = (args.target + args.batch_size - 1) // args.batch_size
    estimated_calls = batches * 1.5
    estimated_input = estimated_calls * 1200
    estimated_output = estimated_calls * 1800
    estimate = (
        estimated_input / 1_000_000 * INPUT_USD_PER_M
        + estimated_output / 1_000_000 * OUTPUT_USD_PER_M
    )
    plan = {
        "target_questions": args.target,
        "batch_size": args.batch_size,
        "batches": batches,
        "type_mixes": [[item.value for item in types] for _, types in BATCH_PLAN[:batches]],
        "estimated_model_calls": round(estimated_calls, 1),
        "estimated_tokens": {
            "input": estimated_input,
            "output": estimated_output,
        },
        "estimated_cost_usd": round(estimate, 4),
        "pricing_basis": (
            "DeepSeek off-peak list price, input cache-miss $0.15/M, "
            "output $0.60/M; estimate only, actual usage is recorded per job"
        ),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if not args.live:
        print("[dry-run] 未调用真实模型；确认预算后加 --live。")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="biolearn-phase5-eval-"))
    engine = build_engine(f"sqlite:///{tmp / 'eval.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    subject_id, point_ids = seed(factory)
    settings = effective_ai_settings(Settings())
    print(f"[live] model={settings.ai_model} json_mode={settings.ai_json_mode} temp={tmp}")

    results: list[dict] = []
    for index in range(batches):
        point_indexes, types = BATCH_PLAN[index % len(BATCH_PLAN)]
        selected = [point_ids[i] for i in point_indexes if i < len(point_ids)]
        count = min(args.batch_size, args.target - index * args.batch_size)
        print(f"[batch {index + 1}/{batches}] types={[t.value for t in types]} count={count}")
        result = run_batch(factory, subject_id, selected, types, count, settings)
        results.append(result)
        print(
            f"  status={result['status']} saved={result['saved']} "
            f"skipped={result['skipped']} calls={result['model_calls']} "
            f"repairs={result['format_repairs']} latency={result['latency_seconds']}s"
        )
        if result["error"]:
            print(f"  error_kind={result['error_kind']} error={result['error']}")

    saved_total = sum(item["saved"] for item in results)
    skipped_total = sum(item["skipped"] for item in results)
    failed_batches = sum(1 for item in results if item["status"] == "failed")
    repairs_total = sum(item["format_repairs"] for item in results)
    calls_total = sum(item["model_calls"] for item in results)
    input_total = sum(int(item["tokens"].get("prompt_tokens", 0)) for item in results)
    output_total = sum(int(item["tokens"].get("completion_tokens", 0)) for item in results)
    estimated_cost = (
        input_total / 1_000_000 * INPUT_USD_PER_M
        + output_total / 1_000_000 * OUTPUT_USD_PER_M
    )
    latencies = [item["latency_seconds"] for item in results]
    summary = {
        "plan": plan,
        "target_questions": args.target,
        "saved_questions": saved_total,
        "skipped_questions": skipped_total,
        "failed_batches": failed_batches,
        "completed_batches": sum(1 for item in results if item["status"] == "completed"),
        "format_repairs": repairs_total,
        "model_calls": calls_total,
        "tokens": {
            "prompt": input_total,
            "completion": output_total,
            "total": input_total + output_total,
        },
        "estimated_cost_usd": round(estimated_cost, 6),
        "cost_note": (
            "估算值：DeepSeek 非高峰列表价，输入按 cache miss $0.15/M、"
            "输出 $0.60/M；未计入缓存命中折扣，实际账单以提供商为准"
        ),
        "latency_seconds": {
            "mean": round(mean(latencies), 2) if latencies else 0,
            "max": max(latencies) if latencies else 0,
        },
        "error_kinds": dict(Counter(item["error_kind"] or "none" for item in results)),
        "batches": results,
        "temp_db": str(tmp),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "target_questions", "saved_questions", "skipped_questions",
        "failed_batches", "completed_batches", "format_repairs",
        "model_calls", "tokens", "estimated_cost_usd", "latency_seconds",
        "error_kinds",
    )}, ensure_ascii=False, indent=2))
    print(f"[done] {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
