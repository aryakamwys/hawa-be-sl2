"""
Community Feedback Model
Untuk user reports tentang polusi udara (Reddit-like community feed)
"""
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Enum as SqlEnum, Text, Boolean, Float, ForeignKey, UniqueConstraint, TypeDecorator
from sqlalchemy.sql import func
from app.db.postgres import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class FeedbackStatusEnum(str, Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class CommunityFeedback(Base):
    """Community feedback/report dari user tentang polusi udara"""
    __tablename__ = "community_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # User yang submit (Foreign Key ke users.id)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Data Laporan
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Kategori & Type
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # pollution, health, visibility, odor
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)  # low, medium, high, critical
    
    # Anonymous & Privacy
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # File Attachments
    attachment_paths: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array: ["path1.jpg", "path2.pdf"]
    attachment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Admin Review
    status: Mapped[FeedbackStatusEnum] = mapped_column(
        SqlEnum(FeedbackStatusEnum, native_enum=False, length=20),
        default=FeedbackStatusEnum.PENDING,
        nullable=False,
        index=True
    )
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Engagement (Reddit-like)
    upvotes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    downvotes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="feedbacks")
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by])
    votes: Mapped[list["FeedbackVote"]] = relationship("FeedbackVote", back_populates="feedback", cascade="all, delete-orphan")


class FeedbackVote(Base):
    """Vote dari user untuk feedback (upvote/downvote)"""
    __tablename__ = "feedback_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    feedback_id: Mapped[int] = mapped_column(Integer, ForeignKey("community_feedbacks.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    vote_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "upvote" atau "downvote"
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Unique constraint: satu user hanya bisa vote sekali per feedback
    __table_args__ = (
        UniqueConstraint('feedback_id', 'user_id', name='uq_feedback_vote_user'),
    )
    
    # Relationships
    feedback: Mapped["CommunityFeedback"] = relationship("CommunityFeedback", back_populates="votes")
    user: Mapped["User"] = relationship("User")

