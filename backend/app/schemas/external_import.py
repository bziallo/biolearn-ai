from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

SUPPORTED_SCHEMA_VERSION = "1.0"
MAX_CHAPTERS = 500
MAX_POINTS = 5000
MAX_CHAPTER_DEPTH = 8


class ExternalDocument(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    type: str = Field(default="other", max_length=40)
    summary: str | None = Field(default=None, max_length=8000)


class ExternalSubject(BaseModel):
    id: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=120)


class ExternalChapter(BaseModel):
    id: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    source_slide: int | None = Field(default=None, ge=1)
    children: list["ExternalChapter"] = Field(default_factory=list)


class ExternalSource(BaseModel):
    document_name: str | None = Field(default=None, max_length=300)
    page: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    slide: int | None = Field(default=None, ge=1)
    quote: str | None = Field(default=None, max_length=4000)
    locator: str | None = Field(default=None, max_length=300)


class ExternalKnowledgePoint(BaseModel):
    point_id: str | None = Field(default=None, max_length=80)
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=20000)
    chapter_path: list[str] = Field(default_factory=list, max_length=MAX_CHAPTER_DEPTH)
    category: str = Field(default="basic_concept", max_length=40)
    importance: str | None = Field(default=None, max_length=16)
    key_terms: list[str] = Field(default_factory=list, max_length=30)
    source: ExternalSource = Field(default_factory=ExternalSource)
    prerequisites: list[str] = Field(default_factory=list, max_length=30)
    confidence: float | None = Field(default=None, ge=0, le=1)


class ExternalMetadata(BaseModel):
    model: str | None = Field(default=None, max_length=160)
    generated_at: str | None = Field(default=None, max_length=80)
    shard_index: int | None = Field(default=None, ge=1)
    shard_total: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=4000)


class ExternalImportPayload(BaseModel):
    schema_version: str
    document: ExternalDocument
    subject: ExternalSubject
    chapter_tree: list[ExternalChapter] = Field(default_factory=list)
    knowledge_points: list[ExternalKnowledgePoint] = Field(default_factory=list)
    metadata: ExternalMetadata = Field(default_factory=ExternalMetadata)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: str) -> str:
        if value != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(
                f"不支持的 schema_version：{value!r}；当前仅支持 "
                f"{SUPPORTED_SCHEMA_VERSION}"
            )
        return value

    @model_validator(mode="after")
    def validate_limits(self) -> "ExternalImportPayload":
        chapters = _count_chapters(self.chapter_tree)
        if chapters > MAX_CHAPTERS:
            raise ValueError(f"章节数量超过上限 {MAX_CHAPTERS}")
        if len(self.knowledge_points) > MAX_POINTS:
            raise ValueError(f"知识点数量超过上限 {MAX_POINTS}")
        for chapter in _walk_chapters(self.chapter_tree):
            if _chapter_depth(chapter) > MAX_CHAPTER_DEPTH:
                raise ValueError(f"章节层级超过上限 {MAX_CHAPTER_DEPTH}")
        for point in self.knowledge_points:
            if not point.title.strip():
                raise ValueError("知识点 title 不能为空")
            if len(point.chapter_path) > MAX_CHAPTER_DEPTH:
                raise ValueError(f"知识点 chapter_path 超过 {MAX_CHAPTER_DEPTH} 层")
        return self


def _walk_chapters(nodes: list[ExternalChapter]) -> list[ExternalChapter]:
    result: list[ExternalChapter] = []
    stack = list(nodes)
    while stack:
        node = stack.pop(0)
        result.append(node)
        stack[0:0] = node.children
    return result


def _count_chapters(nodes: list[ExternalChapter]) -> int:
    return len(_walk_chapters(nodes))


def _chapter_depth(node: ExternalChapter) -> int:
    depth = 1
    current = node
    while current.children:
        depth += 1
        current = current.children[0]
    return depth


ExternalChapter.model_rebuild()


def parse_external_payload(raw: Any) -> ExternalImportPayload:
    return ExternalImportPayload.model_validate(raw)


def external_json_schema() -> dict[str, Any]:
    return ExternalImportPayload.model_json_schema()

EXTERNAL_IMPORT_PROMPT = """你是 BioLearn AI 的外部课件分析助手。请阅读整份课件，而不是只看封面或目录，然后严格输出一个 JSON 文件。

必须遵守：
1. 按课件原有结构识别大章节、子章节和知识点，保留真实层级。
2. 提取概念定义、机制原理、实验方法、公式、关键数据和易混淆概念。
3. 每条知识点必须给出原始幻灯片页码或页面编号；无法确认时留空并在 metadata.notes 中说明，禁止编造。
4. 合并重复知识点，但不得把不同概念错误合并。
5. 区分课件明确记载的内容和模型补充的内容；默认不补充课件中不存在的事实。补充内容必须在 content 中明确标注“模型补充”。
6. 对无法确认的信息标记在 metadata.notes 或知识点 needs_review；不要编造来源或页码。
7. 只输出 JSON，不要 Markdown 代码块、解释或前后缀。
8. 如果课件过长无法一次输出完整 JSON，请按 shard 分片输出多个 JSON 文件：
   - 每个分片使用相同的 document、subject、chapter_tree 结构；
   - metadata.shard_index / shard_total 标明分片；
   - 每条知识点提供稳定 point_id（同一知识点在不同分片中保持一致）；
   - 不要静默截断，也不要在未完成时声称已完成。
9. 不要生成数据库 ID；subject 只提供名称或已有学科 id，章节只提供名称/层级。

JSON Schema（schema_version 当前只支持 1.0）：
{schema}

最小示例：
{example}
"""

EXTERNAL_IMPORT_EXAMPLE = {
    "schema_version": "1.0",
    "document": {
        "name": "蛋白质的结构与功能",
        "type": "pptx",
        "summary": "蛋白质结构层次与功能关系",
    },
    "subject": {"id": None, "name": "生物化学"},
    "chapter_tree": [
        {
            "id": "ch1",
            "name": "第一章 蛋白质的分子结构",
            "source_slide": 2,
            "children": [
                {
                    "id": "ch1-1",
                    "name": "第一节 一级结构",
                    "source_slide": 5,
                    "children": [],
                }
            ],
        }
    ],
    "knowledge_points": [
        {
            "point_id": "kp-001",
            "title": "蛋白质一级结构",
            "content": "蛋白质的一级结构是氨基酸的线性排列顺序。",
            "chapter_path": ["第一章 蛋白质的分子结构", "第一节 一级结构"],
            "category": "structure",
            "importance": "high",
            "key_terms": ["氨基酸序列", "肽键"],
            "source": {
                "document_name": "蛋白质的结构与功能",
                "slide": 5,
                "page": None,
                "quote": "蛋白质的一级结构是氨基酸的排列顺序。",
            },
            "prerequisites": ["氨基酸"],
            "confidence": 0.9,
        }
    ],
    "metadata": {
        "model": "external-ai",
        "generated_at": "2026-10-19T12:00:00Z",
        "shard_index": 1,
        "shard_total": 1,
        "notes": "",
    },
}


def build_external_prompt() -> str:
    """Render the prompt without treating JSON braces as format fields."""

    return EXTERNAL_IMPORT_PROMPT.replace(
        "{schema}",
        json.dumps(external_json_schema(), ensure_ascii=False, indent=2),
    ).replace(
        "{example}",
        json.dumps(EXTERNAL_IMPORT_EXAMPLE, ensure_ascii=False, indent=2),
    )
