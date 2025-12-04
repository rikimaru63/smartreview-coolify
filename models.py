"""
SQLAlchemy Models for SmartReview AI
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from database import Base


class Store(Base):
    """店舗情報テーブル"""
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String(50), unique=True, index=True, default="main-store")
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    services = Column(JSON, default=list)  # ["ハイフ", "リフトアップ", ...]
    platform_urls = Column(JSON, default=dict)  # {"google": "", "hotpepper": "", ...}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # リレーション
    reviews = relationship("Review", back_populates="store")

    def to_dict(self):
        """辞書形式に変換（API互換性のため）"""
        return {
            "store_id": self.store_id,
            "name": self.name,
            "description": self.description or "",
            "address": self.address or "",
            "phone": self.phone or "",
            "services": self.services or [],
            "platform_urls": self.platform_urls or {},
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class Review(Base):
    """レビュー履歴テーブル"""
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String(50), ForeignKey("stores.store_id"), nullable=False)
    platform = Column(String(50), nullable=False)  # google, hotpepper, booking, tripadvisor
    rating = Column(Integer, nullable=False)
    services = Column(JSON, default=list)
    user_comment = Column(Text, nullable=True)
    generated_text = Column(Text, nullable=False)
    language = Column(String(10), default="ja")
    created_at = Column(DateTime, default=datetime.utcnow)

    # リレーション
    store = relationship("Store", back_populates="reviews")

    def to_dict(self):
        """辞書形式に変換"""
        return {
            "id": self.id,
            "store_id": self.store_id,
            "platform": self.platform,
            "rating": self.rating,
            "services": self.services or [],
            "user_comment": self.user_comment or "",
            "generated_text": self.generated_text,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class AdminSession(Base):
    """管理者セッションテーブル"""
    __tablename__ = "admin_sessions"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(100), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    @classmethod
    def create_session(cls, token: str, duration_hours: int = 1):
        """新しいセッションを作成"""
        return cls(
            token=token,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=duration_hours)
        )

    def is_valid(self) -> bool:
        """セッションが有効かどうか"""
        return datetime.utcnow() < self.expires_at


# デフォルトの店舗データ（Seedデータ）
DEFAULT_STORE_DATA = {
    "store_id": "main-store",
    "name": "Beauty Salon SAKURA",
    "description": "最新の美容機器を完備した完全個室プライベートサロン",
    "address": "東京都渋谷区表参道1-2-3",
    "phone": "03-1234-5678",
    "services": ["ハイフ", "リフトアップ", "フェイシャル", "ボディケア", "脱毛"],
    "platform_urls": {
        "google": "",
        "hotpepper": "",
        "booking": "",
        "tripadvisor": ""
    }
}
