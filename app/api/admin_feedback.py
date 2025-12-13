"""
Admin Feedback Management API endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_admin
from app.db.postgres import get_db
from app.db.models.user import User
from app.services.feedback.service import FeedbackService
from app.services.feedback.schemas import (
    FeedbackResponse,
    FeedbackListResponse,
    AdminFeedbackStatusUpdate,
    AdminFeedbackNotesUpdate,
    FeedbackStatsResponse
)
from app.api.feedback import _build_feedback_response, _build_author_info

router = APIRouter(prefix="/admin/feedback", tags=["admin-feedback"])


@router.get("", response_model=FeedbackListResponse)
def get_all_feedback(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all feedback reports (admin only)"""
    service = FeedbackService(db)
    result = service.get_all_reports_admin(
        limit=limit,
        offset=offset,
        status=status,
        category=category,
        search=search
    )
    
    # Build response
    reports = []
    for feedback in result["reports"]:
        # Admin can see real user info even if anonymous
        author_info = {
            "id": feedback.user.id,
            "full_name": feedback.user.full_name or "User",
            "is_anonymous": feedback.is_anonymous  # Flag to know it's anonymous in public
        }
        
        # Truncate description for list view
        description = feedback.description
        if len(description) > 200:
            description = description[:200] + "..."
        
        reports.append({
            "id": feedback.id,
            "title": feedback.title,
            "description": description,
            "location": feedback.location,
            "category": feedback.category,
            "severity": feedback.severity,
            "status": feedback.status.value,
            "is_anonymous": feedback.is_anonymous,
            "is_public": feedback.is_public,
            "upvotes": feedback.upvotes,
            "view_count": feedback.view_count,
            "attachment_count": feedback.attachment_count,
            "created_at": feedback.created_at,
            "author": author_info,
            "user_voted": None
        })
    
    return {
        "reports": reports,
        "total": result["total"],
        "limit": limit,
        "offset": offset,
        "stats": result["stats"]
    }


@router.get("/{feedback_id}", response_model=FeedbackResponse)
def get_feedback_detail_admin(
    feedback_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get feedback detail (admin only - can see all info)"""
    from app.db.models.feedback import CommunityFeedback
    
    feedback = db.query(CommunityFeedback).filter(
        CommunityFeedback.id == feedback_id
    ).first()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found"
        )
    
    return _build_feedback_response(feedback, current_admin.id, is_admin=True, db=db)


@router.put("/{feedback_id}/status", response_model=FeedbackResponse)
def update_feedback_status(
    feedback_id: int,
    update_data: AdminFeedbackStatusUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update feedback status (admin only)"""
    service = FeedbackService(db)
    feedback = service.update_feedback_status(
        feedback_id=feedback_id,
        admin_id=current_admin.id,
        new_status=update_data.status,
        admin_notes=update_data.admin_notes
    )
    
    return _build_feedback_response(feedback, current_admin.id, is_admin=True, db=db)


@router.put("/{feedback_id}/notes", response_model=FeedbackResponse)
def update_feedback_notes(
    feedback_id: int,
    update_data: AdminFeedbackNotesUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update feedback admin notes (admin only)"""
    from app.db.models.feedback import CommunityFeedback
    
    feedback = db.query(CommunityFeedback).filter(
        CommunityFeedback.id == feedback_id
    ).first()
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found"
        )
    
    feedback.admin_notes = update_data.admin_notes
    db.commit()
    db.refresh(feedback)
    
    return _build_feedback_response(feedback, current_admin.id, is_admin=True, db=db)


@router.get("/stats", response_model=FeedbackStatsResponse)
def get_feedback_stats(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get feedback statistics (admin only)"""
    service = FeedbackService(db)
    return service.get_feedback_stats()

