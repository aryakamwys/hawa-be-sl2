"""
Pydantic schemas untuk Community Feedback
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class FeedbackSubmitRequest(BaseModel):
    """Request untuk submit feedback"""
    title: str = Field(..., min_length=1, max_length=200, description="Judul laporan")
    description: str = Field(..., min_length=1, max_length=5000, description="Deskripsi detail")
    location: Optional[str] = Field(None, max_length=200, description="Lokasi kejadian")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude")
    category: Optional[str] = Field(None, description="Kategori: pollution, health, visibility, odor")
    severity: Optional[str] = Field(None, description="Tingkat: low, medium, high, critical")
    is_anonymous: bool = Field(False, description="Submit sebagai anonymous")
    is_public: bool = Field(True, description="Tampilkan di community feed")


class FeedbackVoteRequest(BaseModel):
    """Request untuk vote feedback"""
    vote_type: Optional[str] = Field(None, description="upvote, downvote, atau null untuk remove vote")


class AuthorInfo(BaseModel):
    """Author info untuk response (hide jika anonymous)"""
    id: Optional[int] = None
    full_name: str = "Anonymous"
    is_anonymous: bool = False


class FeedbackResponse(BaseModel):
    """Response untuk feedback detail"""
    id: int
    title: str
    description: str
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    is_anonymous: bool
    is_public: bool
    attachment_paths: Optional[list[str]] = None
    attachment_count: int
    status: str
    admin_notes: Optional[str] = None
    upvotes: int
    downvotes: int
    view_count: int
    created_at: datetime
    updated_at: datetime
    author: AuthorInfo
    user_voted: Optional[str] = None  # null, "upvote", atau "downvote"
    is_owner: bool = False  # true jika user yang submit

    class Config:
        from_attributes = True


class FeedbackListItem(BaseModel):
    """Response untuk feedback list (truncated)"""
    id: int
    title: str
    description: str  # Truncated untuk list view
    location: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    status: str
    is_anonymous: bool
    is_public: bool
    upvotes: int
    view_count: int
    attachment_count: int
    created_at: datetime
    author: AuthorInfo
    user_voted: Optional[str] = None

    class Config:
        from_attributes = True


class FeedbackListResponse(BaseModel):
    """Response untuk feedback list dengan pagination"""
    reports: list[FeedbackListItem]
    total: int
    limit: int
    offset: int


class FeedbackVoteResponse(BaseModel):
    """Response untuk vote action"""
    feedback_id: int
    upvotes: int
    downvotes: int
    user_voted: Optional[str] = None


class AdminFeedbackStatusUpdate(BaseModel):
    """Request untuk update status (admin only)"""
    status: str = Field(..., description="pending, reviewed, resolved, rejected")
    admin_notes: Optional[str] = None


class AdminFeedbackNotesUpdate(BaseModel):
    """Request untuk update notes (admin only)"""
    admin_notes: str


class FeedbackStatsResponse(BaseModel):
    """Response untuk feedback statistics (admin only)"""
    total_reports: int
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_severity: dict[str, int]
    recent_7_days: int
    recent_30_days: int






