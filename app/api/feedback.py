"""
Community Feedback API endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_current_admin
from app.db.postgres import get_db
from app.db.models.user import User
from app.services.feedback.service import FeedbackService
from app.services.feedback.schemas import (
    FeedbackSubmitRequest,
    FeedbackResponse,
    FeedbackListItem,
    FeedbackListResponse,
    FeedbackVoteRequest,
    FeedbackVoteResponse,
    AdminFeedbackStatusUpdate,
    AdminFeedbackNotesUpdate,
    FeedbackStatsResponse
)
from app.core.file_storage import parse_attachment_paths
from app.db.models.feedback import FeedbackVote, CommunityFeedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _build_author_info(feedback: CommunityFeedback, is_admin: bool = False) -> dict:
    """Build author info, hide if anonymous (unless admin)"""
    if feedback.is_anonymous and not is_admin:
        return {
            "id": None,
            "full_name": "Anonymous",
            "is_anonymous": True
        }
    else:
        # Ensure user relationship is loaded
        if not hasattr(feedback, 'user') or feedback.user is None:
            return {
                "id": None,
                "full_name": "Unknown User",
                "is_anonymous": False
            }
        return {
            "id": feedback.user.id,
            "full_name": feedback.user.full_name or "User",
            "is_anonymous": feedback.is_anonymous
        }


def _build_feedback_response(feedback: CommunityFeedback, current_user_id: Optional[int] = None, is_admin: bool = False, db: Optional[Session] = None) -> dict:
    """Build feedback response with author info and vote status"""
    # Get user vote
    user_voted = None
    if current_user_id and db:
        vote = db.query(FeedbackVote).filter(
            FeedbackVote.feedback_id == feedback.id,
            FeedbackVote.user_id == current_user_id
        ).first()
        if vote:
            user_voted = vote.vote_type
    
    # Parse attachment paths
    attachment_paths = parse_attachment_paths(feedback.attachment_paths)
    
    return {
        "id": feedback.id,
        "title": feedback.title,
        "description": feedback.description,
        "location": feedback.location,
        "latitude": feedback.latitude,
        "longitude": feedback.longitude,
        "category": feedback.category,
        "severity": feedback.severity,
        "is_anonymous": feedback.is_anonymous,
        "is_public": feedback.is_public,
        "attachment_paths": attachment_paths,
        "attachment_count": feedback.attachment_count,
        "status": feedback.status.value,
        "admin_notes": feedback.admin_notes if is_admin else None,
        "upvotes": feedback.upvotes,
        "downvotes": feedback.downvotes,
        "view_count": feedback.view_count,
        "created_at": feedback.created_at,
        "updated_at": feedback.updated_at,
        "author": _build_author_info(feedback, is_admin),
        "user_voted": user_voted,
        "is_owner": current_user_id == feedback.user_id if current_user_id else False
    }


@router.post("/submit", status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    title: str = Form(...),
    description: str = Form(...),
    location: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    category: Optional[str] = Form(None),
    severity: Optional[str] = Form(None),
    is_anonymous: bool = Form(False),
    is_public: bool = Form(True),
    files: Optional[list[UploadFile]] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a new feedback/report"""
    service = FeedbackService(db)
    
    data = FeedbackSubmitRequest(
        title=title,
        description=description,
        location=location,
        latitude=latitude,
        longitude=longitude,
        category=category,
        severity=severity,
        is_anonymous=is_anonymous,
        is_public=is_public
    )
    
    try:
        # Convert files to list if single file
        file_list = files if isinstance(files, list) else [files] if files else None
        
        feedback = await service.create_feedback(
            user_id=current_user.id,
            data=data,
            files=file_list
        )
        
        return {
            "id": feedback.id,
            "title": feedback.title,
            "status": feedback.status.value,
            "is_anonymous": feedback.is_anonymous,
            "is_public": feedback.is_public,
            "created_at": feedback.created_at,
            "message": "Report submitted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating feedback: {str(e)}"
        )


@router.get("", response_model=FeedbackListResponse)
def get_community_feed(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: str = Query("newest", regex="^(newest|upvotes|views)$"),
    status_filter: Optional[str] = Query(None, description="Comma-separated: pending,reviewed,resolved", alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get community feed (public reports)"""
    try:
        service = FeedbackService(db)
        result = service.get_community_feed(
            current_user_id=current_user.id,
            limit=limit,
            offset=offset,
            category=category,
            severity=severity,
            location=location,
            search=search,
            sort=sort,
            status_filter=status_filter
        )
        
        # Build response
        reports = []
        for feedback in result["reports"]:
            try:
                user_voted = result["user_votes"].get(feedback.id)
                
                # Truncate description for list view
                description = feedback.description or ""
                if len(description) > 200:
                    description = description[:200] + "..."
                
                reports.append({
                    "id": feedback.id,
                    "title": feedback.title or "",
                    "description": description,
                    "location": feedback.location,
                    "category": feedback.category,
                    "severity": feedback.severity,
                    "status": feedback.status.value,
                    "is_anonymous": feedback.is_anonymous,
                    "is_public": feedback.is_public,
                    "upvotes": feedback.upvotes or 0,
                    "view_count": feedback.view_count or 0,
                    "attachment_count": feedback.attachment_count or 0,
                    "created_at": feedback.created_at,
                    "author": _build_author_info(feedback, is_admin=False),
                    "user_voted": user_voted
                })
            except Exception as e:
                # Skip problematic feedback and continue
                print(f"Error processing feedback {feedback.id}: {e}")
                continue
        
        return {
            "reports": reports,
            "total": result["total"],
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading feed: {str(e)}"
        )


@router.get("/{feedback_id}", response_model=FeedbackResponse)
def get_feedback_detail(
    feedback_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get feedback detail"""
    service = FeedbackService(db)
    feedback = service.get_feedback_detail(feedback_id, current_user.id)
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback not found"
        )
    
    return _build_feedback_response(feedback, current_user.id, is_admin=False, db=db)


@router.post("/{feedback_id}/vote", response_model=FeedbackVoteResponse)
def vote_feedback(
    feedback_id: int,
    vote_data: FeedbackVoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Vote on a feedback"""
    service = FeedbackService(db)
    result = service.vote_feedback(
        feedback_id=feedback_id,
        user_id=current_user.id,
        vote_type=vote_data.vote_type
    )
    return result


@router.get("/my-reports", response_model=FeedbackListResponse)
def get_my_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's own reports"""
    service = FeedbackService(db)
    result = service.get_my_reports(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        status=status
    )
    
    reports = []
    for feedback in result["reports"]:
        reports.append({
            "id": feedback.id,
            "title": feedback.title,
            "description": feedback.description[:200] + "..." if len(feedback.description) > 200 else feedback.description,
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
            "author": _build_author_info(feedback, is_admin=False),
            "user_voted": None
        })
    
    return {
        "reports": reports,
        "total": result["total"],
        "limit": limit,
        "offset": offset
    }

