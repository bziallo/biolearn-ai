from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _config_for(database_path: Path) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{database_path.as_posix()}",
    )
    return config


def test_migrations_replay_and_seed_initial_subjects(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    config = _config_for(database_path)

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        inspector = inspect(engine)
        assert {
            "subjects",
            "chapters",
            "import_preferences",
            "import_jobs",
            "question_generation_jobs",
            "questions",
            "question_knowledge_points",
            "practice_sessions",
            "practice_answers",
        } <= set(inspector.get_table_names())
        job_columns = {
            column["name"]
            for column in inspector.get_columns("knowledge_extraction_jobs")
        }
        assert "cancel_requested" in job_columns
        assert "timings" in job_columns
        chapter_columns = {
            column["name"] for column in inspector.get_columns("chapters")
        }
        assert {
            "source_document_id",
            "source_import_job_id",
            "source_slide",
        } <= chapter_columns
        import_columns = {
            column["name"] for column in inspector.get_columns("import_jobs")
        }
        assert {
            "source_type",
            "payload",
            "duplicate_strategy",
            "timings",
        } <= import_columns
        point_columns = {
            column["name"] for column in inspector.get_columns("knowledge_points")
        }
        assert {"importance", "prerequisites", "external_id"} <= point_columns
        question_columns = {
            column["name"] for column in inspector.get_columns("questions")
        }
        assert {
            "options",
            "answer",
            "grading_rule",
            "status",
            "difficulty",
            "generation_job_id",
            "duplicate_of_id",
        } <= question_columns
        practice_columns = {
            column["name"] for column in inspector.get_columns("practice_answers")
        }
        assert {
            "session_id",
            "question_id",
            "user_answer",
            "is_correct",
            "score",
            "graded_by",
        } <= practice_columns
        with engine.connect() as connection:
            count = connection.execute(
                text("SELECT COUNT(*) FROM subjects")
            ).scalar_one()
            assert count == 10
            names = connection.execute(
                text("SELECT name FROM subjects ORDER BY sort_order")
            ).scalars().all()
            assert names[0] == "生物化学"
            assert names[-1] == "药理学"
    finally:
        engine.dispose()

    command.downgrade(config, "base")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        assert "subjects" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.connect() as connection:
            count = connection.execute(
                text("SELECT COUNT(*) FROM subjects")
            ).scalar_one()
            assert count == 10
    finally:
        engine.dispose()
