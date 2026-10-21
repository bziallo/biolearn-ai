"""Seed editable example subjects.

Revision ID: 0003_seed_initial_subjects
Revises: 0002_subjects_chapters
Create Date: 2026-10-19
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision: str = "0003_seed_initial_subjects"
down_revision: str | Sequence[str] | None = "0002_subjects_chapters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_SUBJECTS = [
    (
        "biochemistry",
        "生物化学",
        "从分子层面理解生命过程的化学基础。",
        "#2dd4bf",
        "🧬",
        0,
    ),
    (
        "microbiology",
        "微生物学",
        "研究细菌、病毒、真菌等微生物的结构、代谢与致病机制。",
        "#38bdf8",
        "🦠",
        10,
    ),
    (
        "cell-biology",
        "细胞生物学",
        "探索细胞结构、功能、信号传导与生命周期。",
        "#a78bfa",
        "🧫",
        20,
    ),
    (
        "molecular-biology",
        "分子生物学",
        "研究基因复制、转录、翻译及分子调控机制。",
        "#f472b6",
        "🧪",
        30,
    ),
    (
        "genetics",
        "遗传学",
        "理解遗传变异、基因传递与性状表达的规律。",
        "#f59e0b",
        "🧬",
        40,
    ),
    (
        "immunology",
        "免疫学",
        "学习先天与适应性免疫、免疫应答及相关疾病。",
        "#34d399",
        "🛡️",
        50,
    ),
    (
        "physiology",
        "生理学",
        "研究人体各系统正常功能及其调节机制。",
        "#fb7185",
        "❤️",
        60,
    ),
    (
        "bioinformatics",
        "生物信息学",
        "用计算方法分析序列、结构与组学数据。",
        "#60a5fa",
        "💻",
        70,
    ),
    (
        "biotechnology",
        "生物技术与基因工程",
        "学习基因编辑、表达系统与产业化应用。",
        "#c084fc",
        "🌱",
        80,
    ),
    (
        "pharmacology",
        "药理学",
        "研究药物作用机制、代谢动力学与临床用药。",
        "#fbbf24",
        "💊",
        90,
    ),
]

subjects_table = sa.table(
    "subjects",
    sa.column("id", sa.String(length=36)),
    sa.column("name", sa.String(length=120)),
    sa.column("description", sa.Text()),
    sa.column("color", sa.String(length=16)),
    sa.column("icon", sa.String(length=32)),
    sa.column("sort_order", sa.Integer()),
)


def _seed_id(slug: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"biolearn:subject:{slug}"))


def upgrade() -> None:
    op.bulk_insert(
        subjects_table,
        [
            {
                "id": _seed_id(slug),
                "name": name,
                "description": description,
                "color": color,
                "icon": icon,
                "sort_order": sort_order,
            }
            for slug, name, description, color, icon, sort_order in SEED_SUBJECTS
        ],
    )


def downgrade() -> None:
    seed_ids = [_seed_id(slug) for slug, *_ in SEED_SUBJECTS]
    op.execute(
        subjects_table.delete().where(subjects_table.c.id.in_(seed_ids))
    )
