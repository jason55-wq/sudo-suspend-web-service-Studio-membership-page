import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

    db_url = os.environ.get("DATABASE_URL")
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    if not db_url and os.environ.get("RENDER"):
        db_url = "sqlite:////opt/render/project/src/data/member.db"

    SQLALCHEMY_DATABASE_URI = db_url or f"sqlite:///{BASE_DIR / 'local.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MEMBER_FILES_DIR = os.environ.get(
        "MEMBER_FILES_DIR",
        str(BASE_DIR / "member_files")
    )
