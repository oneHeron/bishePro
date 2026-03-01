import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

engine_kwargs = {"future": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import db_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_run_columns()


def _ensure_run_columns() -> None:
    inspector = inspect(engine)
    if "runs" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("runs")}
    required = {
        "method_id": "VARCHAR(64)",
        "dataset_id": "VARCHAR(64)",
        "metrics": "JSON",
        "results": "JSON",
        "duration": "FLOAT",
        "started_at": "DATETIME",
        "finished_at": "DATETIME",
    }

    with engine.begin() as conn:
        for name, sql_type in required.items():
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE runs ADD COLUMN {name} {sql_type}"))
