"""Database engine and session management."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import yaml

from mas.db.models import Base

DEFAULT_DB_URL = "sqlite:///./mas.db"


def get_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    if os.path.exists("config.yaml"):
        try:
            with open("config.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                if cfg and "database" in cfg and "url" in cfg["database"]:
                    return cfg["database"]["url"]
        except Exception:
            pass
    return DEFAULT_DB_URL


_engine = None
_SessionFactory = None


def get_engine(db_url: str = None):
    global _engine
    url = db_url or get_db_url()
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, connect_args=connect_args)
    return engine


def init_db(engine=None):
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)


def get_session(engine=None) -> Session:
    global _SessionFactory
    eng = engine or get_engine()
    if _SessionFactory is None or _SessionFactory.kw.get("bind") != eng:
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    return _SessionFactory()
