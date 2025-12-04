"""
Database connection and session management for SmartReview AI
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 環境変数からDATABASE_URLを取得
# Coolify/PostgreSQL: postgresql://user:password@host:5432/dbname
# ローカル開発用SQLite: sqlite:///./smartreview.db
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./smartreview.db"
)

# DATABASE_URLの補正処理
# Coolify等の環境では postgres:// で渡されることがあるが、
# SQLAlchemy 1.4+ では postgresql:// が必要
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLiteの場合は接続引数を調整
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(DATABASE_URL)

# セッションファクトリ
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# モデルのベースクラス
Base = declarative_base()


def get_db():
    """
    FastAPI Dependencyとして使用するDBセッション取得関数
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    データベース初期化 - テーブル作成
    """
    from models import Store, Review, AdminSession  # 循環インポート回避
    Base.metadata.create_all(bind=engine)
    print("[DB] Tables created successfully")
