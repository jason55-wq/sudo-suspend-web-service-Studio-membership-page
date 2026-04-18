from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    _database_url = os.getenv("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI = (
        _normalize_database_url(_database_url)
        if _database_url
        else f"sqlite:///{(BASE_DIR / 'member.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    MEMBER_FILES_DIR = Path(os.getenv("MEMBER_FILES_DIR", str(BASE_DIR / "member_files")))
