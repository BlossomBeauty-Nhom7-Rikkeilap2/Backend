from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from app.config import settings

# Khởi tạo SQLAlchemy Engine
# Hỗ trợ pool_pre_ping để tự động khôi phục kết nối khi MySQL / TiDB timeout
connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    connect_args = {"check_same_thread": False}
elif "tidbcloud.com" in settings.DATABASE_URL or "ssl" in settings.DATABASE_URL:
    try:
        import ssl
        import certifi
        connect_args["ssl"] = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG and settings.APP_ENV == "development"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI Dependency: Cung cấp Database Session cho mỗi HTTP request.
    Tự động đóng session sau khi request hoàn tất.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
