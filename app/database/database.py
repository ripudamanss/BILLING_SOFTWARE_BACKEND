from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
from urllib.parse import quote_plus
import os

load_dotenv()

DB_USER = os.getenv("DB_USER") or ""
db_password_env = os.getenv("DB_PASSWORD")
DB_PASSWORD = quote_plus(db_password_env) if db_password_env else ""
DB_HOST = os.getenv("DB_HOST") or ""
DB_PORT = os.getenv("DB_PORT") or ""
DB_NAME = os.getenv("DB_NAME") or ""

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()