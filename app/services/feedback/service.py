"""
Feedback Service untuk Community Feedback
"""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from fastapi import HTTPException, status

from app.db.models.feedback import CommunityFeedback, FeedbackVote, FeedbackStatusEnum
from app.db.models.user import User
from app.services.feedback.schemas import FeedbackSubmitRequest
from app.core.file_storage import (
    save_feedback_files,
    parse_attachment_paths,
    serialize_attachment_paths,
    delete_feedback_files
)


class FeedbackService:
    def __init__(self, db: Session) -> None:
        self.db = db

    async def create_feedback(
        self,
        user_id: int,
        data: FeedbackSubmitRequest,
        files: Optional[list] = None
    ) -> CommunityFeedback:
        """Create a new feedback/report"""
        try:
            # Save files if provided
            attachment_paths = []
            if files and len(files) > 0:
                # Create feedback first to get ID
                feedback = CommunityFeedback(
                    user_id=user_id,
                    title=data.title,
                    description=data.description,
                    location=data.location,
                    latitude=data.latitude,
                    longitude=data.longitude,
                    category=data.category,
                    severity=data.severity,
                    is_anonymous=data.is_anonymous,
                    is_public=data.is_public,
                    status=FeedbackStatusEnum.PENDING,
                    attachment_count=0
                )
                self.db.add(feedback)
                self.db.flush()  # Get ID without committing
                
            # Save files
            try:
                saved_paths = await save_feedback_files(feedback.id, files)
                attachment_paths = saved_paths
                feedback.attachment_paths = serialize_attachment_paths(saved_paths)
                feedback.attachment_count = len(saved_paths)
            except Exception as e:
                self.db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error saving files: {str(e)}"
                )
            else:
                feedback = CommunityFeedback(
                    user_id=user_id,
                    title=data.title,
                    description=data.description,
                    location=data.location,
                    latitude=data.latitude,
                    longitude=data.longitude,
                    category=data.category,
                    severity=data.severity,
                    is_anonymous=data.is_anonymous,
                    is_public=data.is_public,
                    status=FeedbackStatusEnum.PENDING,
                    attachment_paths=None,
                    attachment_count=0
                )
                self.db.add(feedback)

            self.db.commit()
            self.db.refresh(feedback)
            return feedback
        except Exception as e:
            self.db.rollback()
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error creating feedback: {str(e)}"
            )

    def get_community_feed(
        self,
        current_user_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        location: Optional[str] = None,
        search: Optional[str] = None,
        sort: str = "newest",
        status_filter: Optional[str] = None
    ) -> dict:
        """Get community feed (public reports)"""
        # Default status filter: exclude rejected
        if status_filter is None:
            status_filter = "pending,reviewed,resolved"
        
        status_list = [s.strip() for s in status_filter.split(",")] if status_filter else []
        
        from sqlalchemy.orm import joinedload
        query = self.db.query(CommunityFeedback).options(
            joinedload(CommunityFeedback.user)
        ).filter(
            CommunityFeedback.is_public == True
        )
        
        # Filter by status - convert to lowercase to match enum values
        if status_list:
            # With native_enum=False, SQLAlchemy stores enum values as strings
            # So we can compare directly with lowercase strings
            status_values = [s.lower().strip() for s in status_list]
            query = query.filter(CommunityFeedback.status.in_(status_values))
        
        # Filter by category
        if category:
            query = query.filter(CommunityFeedback.category == category)
        
        # Filter by severity
        if severity:
            query = query.filter(CommunityFeedback.severity == severity)
        
        # Search
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    CommunityFeedback.title.ilike(search_term),
                    CommunityFeedback.description.ilike(search_term),
                    CommunityFeedback.location.ilike(search_term)
                )
            )
        
        # Location filter
        if location:
            query = query.filter(CommunityFeedback.location.ilike(f"%{location}%"))
        
        # Sort
        if sort == "upvotes":
            query = query.order_by(desc(CommunityFeedback.upvotes))
        elif sort == "views":
            query = query.order_by(desc(CommunityFeedback.view_count))
        else:  # newest
            query = query.order_by(desc(CommunityFeedback.created_at))
        
        # Get total count
        total = query.count()
        
        # Pagination
        feedbacks = query.offset(offset).limit(limit).all()
        
        # Get user votes for current user
        user_votes = {}
        if current_user_id and feedbacks:
            feedback_ids = [f.id for f in feedbacks]
            if feedback_ids:
                vote_records = self.db.query(FeedbackVote).filter(
                    FeedbackVote.user_id == current_user_id,
                    FeedbackVote.feedback_id.in_(feedback_ids)
                ).all()
                user_votes = {v.feedback_id: v.vote_type for v in vote_records}
        
        return {
            "reports": feedbacks,
            "total": total,
            "limit": limit,
            "offset": offset,
            "user_votes": user_votes
        }

    def get_feedback_detail(
        self,
        feedback_id: int,
        current_user_id: Optional[int] = None
    ) -> Optional[CommunityFeedback]:
        """Get feedback detail and increment view count"""
        feedback = self.db.query(CommunityFeedback).filter(
            CommunityFeedback.id == feedback_id
        ).first()
        
        if not feedback:
            return None
        
        # Increment view count
        feedback.view_count += 1
        self.db.commit()
        self.db.refresh(feedback)
        
        return feedback

    def vote_feedback(
        self,
        feedback_id: int,
        user_id: int,
        vote_type: Optional[str]  # "upvote", "downvote", or None to remove
    ) -> dict:
        """Vote on a feedback"""
        feedback = self.db.query(CommunityFeedback).filter(
            CommunityFeedback.id == feedback_id
        ).first()
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
        
        # Check existing vote
        existing_vote = self.db.query(FeedbackVote).filter(
            FeedbackVote.feedback_id == feedback_id,
            FeedbackVote.user_id == user_id
        ).first()
        
        if vote_type is None:
            # Remove vote
            if existing_vote:
                if existing_vote.vote_type == "upvote":
                    feedback.upvotes = max(0, feedback.upvotes - 1)
                elif existing_vote.vote_type == "downvote":
                    feedback.downvotes = max(0, feedback.downvotes - 1)
                self.db.delete(existing_vote)
                self.db.commit()
                return {
                    "feedback_id": feedback_id,
                    "upvotes": feedback.upvotes,
                    "downvotes": feedback.downvotes,
                    "user_voted": None
                }
        else:
            # Add or update vote
            if existing_vote:
                # Update existing vote
                old_type = existing_vote.vote_type
                existing_vote.vote_type = vote_type
                
                # Adjust counts
                if old_type == "upvote" and vote_type == "downvote":
                    feedback.upvotes = max(0, feedback.upvotes - 1)
                    feedback.downvotes += 1
                elif old_type == "downvote" and vote_type == "upvote":
                    feedback.downvotes = max(0, feedback.downvotes - 1)
                    feedback.upvotes += 1
            else:
                # Create new vote
                new_vote = FeedbackVote(
                    feedback_id=feedback_id,
                    user_id=user_id,
                    vote_type=vote_type
                )
                self.db.add(new_vote)
                
                # Adjust counts
                if vote_type == "upvote":
                    feedback.upvotes += 1
                elif vote_type == "downvote":
                    feedback.downvotes += 1
            
            self.db.commit()
            self.db.refresh(feedback)
            
            return {
                "feedback_id": feedback_id,
                "upvotes": feedback.upvotes,
                "downvotes": feedback.downvotes,
                "user_voted": vote_type
            }

    def get_my_reports(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None
    ) -> dict:
        """Get user's own reports"""
        query = self.db.query(CommunityFeedback).filter(
            CommunityFeedback.user_id == user_id
        )
        
        if status:
            query = query.filter(CommunityFeedback.status == FeedbackStatusEnum(status.lower()))
        
        total = query.count()
        feedbacks = query.order_by(desc(CommunityFeedback.created_at)).offset(offset).limit(limit).all()
        
        return {
            "reports": feedbacks,
            "total": total,
            "limit": limit,
            "offset": offset
        }

    def get_all_reports_admin(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> dict:
        """Get all reports for admin (with stats)"""
        query = self.db.query(CommunityFeedback)
        
        # Filters
        if status:
            query = query.filter(CommunityFeedback.status == FeedbackStatusEnum(status.lower()))
        
        if category:
            query = query.filter(CommunityFeedback.category == category)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    CommunityFeedback.title.ilike(search_term),
                    CommunityFeedback.description.ilike(search_term),
                    CommunityFeedback.location.ilike(search_term)
                )
            )
        
        total = query.count()
        feedbacks = query.order_by(desc(CommunityFeedback.created_at)).offset(offset).limit(limit).all()
        
        # Get stats
        stats = {
            "pending": self.db.query(CommunityFeedback).filter(
                CommunityFeedback.status == FeedbackStatusEnum.PENDING
            ).count(),
            "reviewed": self.db.query(CommunityFeedback).filter(
                CommunityFeedback.status == FeedbackStatusEnum.REVIEWED
            ).count(),
            "resolved": self.db.query(CommunityFeedback).filter(
                CommunityFeedback.status == FeedbackStatusEnum.RESOLVED
            ).count(),
            "rejected": self.db.query(CommunityFeedback).filter(
                CommunityFeedback.status == FeedbackStatusEnum.REJECTED
            ).count(),
        }
        
        return {
            "reports": feedbacks,
            "total": total,
            "limit": limit,
            "offset": offset,
            "stats": stats
        }

    def update_feedback_status(
        self,
        feedback_id: int,
        admin_id: int,
        new_status: str,
        admin_notes: Optional[str] = None
    ) -> CommunityFeedback:
        """Update feedback status (admin only)"""
        feedback = self.db.query(CommunityFeedback).filter(
            CommunityFeedback.id == feedback_id
        ).first()
        
        if not feedback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Feedback not found"
            )
        
        feedback.status = FeedbackStatusEnum(new_status.lower())
        feedback.reviewed_by = admin_id
        feedback.reviewed_at = datetime.utcnow()
        
        if admin_notes:
            feedback.admin_notes = admin_notes
        
        self.db.commit()
        self.db.refresh(feedback)
        return feedback

    def get_feedback_stats(self) -> dict:
        """Get feedback statistics (admin only)"""
        total = self.db.query(CommunityFeedback).count()
        
        # By status
        by_status = {
            "pending": self.db.query(CommunityFeedback).filter(
                CommunityFeedback.status == FeedbackStatusEnum.PENDING
            ).count(),
            "reviewed": self.db.query(CommunityFeedback).filter(
                CommunityFeedback.status == FeedbackStatusEnum.REVIEWED
            ).count(),
            "resolved": self.db.query(CommunityFeedback).filter(
                CommunityFeedback.status == FeedbackStatusEnum.RESOLVED
            ).count(),
            "rejected": self.db.query(CommunityFeedback).filter(
                CommunityFeedback.status == FeedbackStatusEnum.REJECTED
            ).count(),
        }
        
        # By category
        by_category = {}
        categories = self.db.query(CommunityFeedback.category, func.count(CommunityFeedback.id)).group_by(
            CommunityFeedback.category
        ).all()
        for cat, count in categories:
            if cat:
                by_category[cat] = count
        
        # By severity
        by_severity = {}
        severities = self.db.query(CommunityFeedback.severity, func.count(CommunityFeedback.id)).group_by(
            CommunityFeedback.severity
        ).all()
        for sev, count in severities:
            if sev:
                by_severity[sev] = count
        
        # Recent
        seven_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        seven_days_ago = seven_days_ago.replace(day=seven_days_ago.day - 7)
        
        recent_7_days = self.db.query(CommunityFeedback).filter(
            CommunityFeedback.created_at >= seven_days_ago
        ).count()
        
        thirty_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        thirty_days_ago = thirty_days_ago.replace(day=thirty_days_ago.day - 30)
        
        recent_30_days = self.db.query(CommunityFeedback).filter(
            CommunityFeedback.created_at >= thirty_days_ago
        ).count()
        
        return {
            "total_reports": total,
            "by_status": by_status,
            "by_category": by_category,
            "by_severity": by_severity,
            "recent_7_days": recent_7_days,
            "recent_30_days": recent_30_days
        }

