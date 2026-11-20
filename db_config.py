# Database Configuration
# Credentials are NOT stored here. They come from:
#   1. .streamlit/secrets.toml  [postgres] section  (local PC + Streamlit Cloud)
#   2. Environment variables PGHOST / PGPORT / PGDATABASE / PGUSER / PGPASSWORD
#      (PGSSLMODE optional) — if PGHOST is set these take priority over 1.
# secrets.toml is in .gitignore — never commit it!

import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


def _load_config():
    cfg = {}
    # PGHOST set → env vars win (lets us point the local app at Supabase for testing)
    if not os.getenv("PGHOST"):
        try:
            import streamlit as st
            if "postgres" in st.secrets:
                cfg = dict(st.secrets["postgres"])
        except Exception:
            pass  # no secrets.toml → fall back to env vars

    config = {
        "host":     cfg.get("host",     os.getenv("PGHOST", "localhost")),
        "port":     int(cfg.get("port", os.getenv("PGPORT", 5432))),
        "database": cfg.get("database", os.getenv("PGDATABASE", "fleet_ops_db")),
        "user":     cfg.get("user",     os.getenv("PGUSER", "postgres")),
        "password": cfg.get("password", os.getenv("PGPASSWORD")),
    }
    # Supabase / cloud DBs need SSL → set sslmode = "require" in secrets
    sslmode = cfg.get("sslmode", os.getenv("PGSSLMODE"))
    if sslmode:
        config["sslmode"] = sslmode
    if not config["password"]:
        raise RuntimeError(
            "Database password not set. Add a [postgres] section to "
            ".streamlit/secrets.toml (see secrets.toml.example)."
        )
    return config


# PostgreSQL connection config (for psycopg2)
DB_CONFIG = _load_config()

_engine = None

# SQLAlchemy engine (for pandas) — created ONCE and reused,
# so we don't open a new connection pool on every query
def get_engine():
    global _engine
    if _engine is None:
        query = {"sslmode": DB_CONFIG["sslmode"]} if "sslmode" in DB_CONFIG else {}
        url = URL.create(
            "postgresql+psycopg2",
            username=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["database"],
            query=query,
        )
        _engine = create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)
    return _engine
