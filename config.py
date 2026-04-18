from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'member.db').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MEMBER_FILES_DIR = Path(os.getenv("MEMBER_FILES_DIR", str(BASE_DIR / "member_files")))
