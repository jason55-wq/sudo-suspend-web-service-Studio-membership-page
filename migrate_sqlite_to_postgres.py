from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text

from app import app
from extensions import db


BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB = BASE_DIR / "member.db"
TABLES = ["users", "products", "orders", "order_items"]


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def reset_sequences(conn) -> None:
    for table in TABLES:
        sequence_name = conn.execute(
            text("select pg_get_serial_sequence(:table_name, 'id')"),
            {"table_name": table},
        ).scalar()
        if not sequence_name:
            continue

        max_id = conn.execute(text(f"select coalesce(max(id), 0) from {table}")).scalar_one()
        conn.execute(
            text("select setval(:sequence_name, :next_value, true)"),
            {"sequence_name": sequence_name, "next_value": max_id},
        )


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    if not SQLITE_DB.exists():
        raise SystemExit(f"SQLite database not found: {SQLITE_DB}")

    database_url = normalize_database_url(database_url)
    engine = create_engine(database_url)

    with app.app_context():
        db.create_all()

    source = sqlite3.connect(SQLITE_DB)
    source.row_factory = sqlite3.Row

    with engine.begin() as conn:
        counts = {
            table: conn.execute(text(f"select count(*) from {table}")).scalar_one()
            for table in TABLES
        }
        if any(counts.values()):
            raise SystemExit(
                "Destination database is not empty; aborting to avoid overwriting data. "
                f"Current counts: {counts}"
            )

        for table in TABLES:
            rows = source.execute(f"select * from {table}").fetchall()
            if not rows:
                continue

            columns = rows[0].keys()
            column_list = ", ".join(columns)
            placeholder_list = ", ".join(f":{column}" for column in columns)
            insert_sql = text(
                f"insert into {table} ({column_list}) values ({placeholder_list})"
            )
            conn.execute(insert_sql, [dict(row) for row in rows])

        reset_sequences(conn)

    print("Migration completed successfully.")


if __name__ == "__main__":
    main()
