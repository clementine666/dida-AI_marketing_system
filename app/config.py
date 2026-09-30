from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic_settings import BaseSettings


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_type: str = "sqlite"
    sqlite_path: str = "data/marketing.db"
    postgresql_url: str = "postgresql://user:password@localhost:5432/marketing"
    events_file: str = "data/raw/ods_amplitude_events.csv"
    users_file: str = "data/raw/ods_amplitude_users.csv"
    funnel_file: str = "data/raw/dwd_hotel_shopping_funnel_detai.csv"
    orders_file: str = "data/raw/channelbooking_v2.csv"
    generate_sample_if_missing: bool = True
    sample_size: int = 10000
    daily_sync_hour: int = 2
    hourly_monitor: bool = True
    t_minus_days: int = 1
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    @property
    def database_url(self) -> str:
        if self.database_type == "postgresql":
            return self.postgresql_url
        db_path = ROOT_DIR / self.sqlite_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.as_posix()}"

    def resolve_path(self, relative: str) -> Path:
        path = ROOT_DIR / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


def _load_yaml_config() -> dict[str, Any]:
    config_path = ROOT_DIR / "config.yaml"
    if not config_path.exists():
        return {}
    with config_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache
def get_settings() -> Settings:
    raw = _load_yaml_config()
    db = raw.get("database", {})
    ds = raw.get("data_sources", {})
    etl = raw.get("etl", {})
    api = raw.get("api", {})
    defaults = Settings()
    return Settings(
        database_type=db.get("type", defaults.database_type),
        sqlite_path=db.get("sqlite_path", defaults.sqlite_path),
        postgresql_url=db.get("postgresql_url", defaults.postgresql_url),
        events_file=ds.get("events_file", defaults.events_file),
        users_file=ds.get("users_file", defaults.users_file),
        funnel_file=ds.get("funnel_file", defaults.funnel_file),
        orders_file=ds.get("orders_file", defaults.orders_file),
        generate_sample_if_missing=ds.get("generate_sample_if_missing", defaults.generate_sample_if_missing),
        sample_size=ds.get("sample_size", defaults.sample_size),
        daily_sync_hour=etl.get("daily_sync_hour", defaults.daily_sync_hour),
        hourly_monitor=etl.get("hourly_monitor", defaults.hourly_monitor),
        t_minus_days=etl.get("t_minus_days", defaults.t_minus_days),
        api_host=api.get("host", defaults.api_host),
        api_port=api.get("port", defaults.api_port),
    )
