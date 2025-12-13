"""Compliance routes - untuk industry users"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_industry_user
from app.db.postgres import get_db
from app.db.models.user import User
from app.services.compliance.service import ComplianceService
from app.services.compliance.schemas import (
    ComplianceRecordCreate,
    ComplianceRecordResponse,
    ComplianceStatsResponse
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/generate-from-heatmap", response_model=list[ComplianceRecordResponse])
def generate_compliance_from_heatmap(
    regulatory_threshold_pm25: float = Query(default=35.0, description="Regulatory threshold for PM2.5 (μg/m³)"),
    regulatory_threshold_pm10: float = Query(default=50.0, description="Regulatory threshold for PM10 (μg/m³)"),
    location_filter: Optional[str] = Query(None, description="Filter by location name (optional)"),
    current_user: User = Depends(get_current_industry_user),
    db: Session = Depends(get_db)
):
    """
    Auto-generate compliance records from real-time heatmap data (industry users only)
    This analyzes current heatmap pollution data and creates compliance records automatically
    """
    service = ComplianceService(db)
    try:
        records = service.generate_compliance_from_heatmap(
            user_id=current_user.id,
            regulatory_threshold_pm25=regulatory_threshold_pm25,
            regulatory_threshold_pm10=regulatory_threshold_pm10,
            location_filter=location_filter
        )
        return [
            ComplianceRecordResponse(
                id=r.id,
                user_id=r.user_id,
                emission_pm25=r.emission_pm25,
                emission_pm10=r.emission_pm10,
                regulatory_threshold_pm25=r.regulatory_threshold_pm25,
                regulatory_threshold_pm10=r.regulatory_threshold_pm10,
                compliance_status=r.compliance_status.value,
                notes=r.notes,
                facility_name=r.facility_name,
                recorded_at=r.recorded_at,
                created_at=r.created_at,
                updated_at=r.updated_at
            )
            for r in records
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to generate compliance from heatmap: {str(e)}"
        )


@router.post("/records", response_model=ComplianceRecordResponse, status_code=status.HTTP_201_CREATED)
def create_compliance_record(
    data: ComplianceRecordCreate,
    current_user: User = Depends(get_current_industry_user),
    db: Session = Depends(get_db)
):
    """Create a new compliance record (industry users only)"""
    service = ComplianceService(db)
    try:
        record = service.create_compliance_record(
            user_id=current_user.id,
            data=data
        )
        return ComplianceRecordResponse(
            id=record.id,
            user_id=record.user_id,
            emission_pm25=record.emission_pm25,
            emission_pm10=record.emission_pm10,
            regulatory_threshold_pm25=record.regulatory_threshold_pm25,
            regulatory_threshold_pm10=record.regulatory_threshold_pm10,
            compliance_status=record.compliance_status.value,
            notes=record.notes,
            facility_name=record.facility_name,
            recorded_at=record.recorded_at,
            created_at=record.created_at,
            updated_at=record.updated_at
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create compliance record: {str(e)}"
        )


@router.get("/records", response_model=list[ComplianceRecordResponse])
def get_compliance_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_industry_user),
    db: Session = Depends(get_db)
):
    """Get compliance history (industry users only)"""
    service = ComplianceService(db)
    records = service.get_compliance_history(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        start_date=start_date,
        end_date=end_date
    )
    
    return [
        ComplianceRecordResponse(
            id=r.id,
            user_id=r.user_id,
            emission_pm25=r.emission_pm25,
            emission_pm10=r.emission_pm10,
            regulatory_threshold_pm25=r.regulatory_threshold_pm25,
            regulatory_threshold_pm10=r.regulatory_threshold_pm10,
            compliance_status=r.compliance_status.value,
            notes=r.notes,
            facility_name=r.facility_name,
            recorded_at=r.recorded_at,
            created_at=r.created_at,
            updated_at=r.updated_at
        )
        for r in records
    ]


@router.get("/stats", response_model=ComplianceStatsResponse)
def get_compliance_stats(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_industry_user),
    db: Session = Depends(get_db)
):
    """Get compliance statistics (industry users only)"""
    service = ComplianceService(db)
    stats = service.get_compliance_stats(
        user_id=current_user.id,
        days=days
    )
    
    latest_record = None
    if stats["latest_record"]:
        r = stats["latest_record"]
        latest_record = ComplianceRecordResponse(
            id=r.id,
            user_id=r.user_id,
            emission_pm25=r.emission_pm25,
            emission_pm10=r.emission_pm10,
            regulatory_threshold_pm25=r.regulatory_threshold_pm25,
            regulatory_threshold_pm10=r.regulatory_threshold_pm10,
            compliance_status=r.compliance_status.value,
            notes=r.notes,
            facility_name=r.facility_name,
            recorded_at=r.recorded_at,
            created_at=r.created_at,
            updated_at=r.updated_at
        )
    
    return ComplianceStatsResponse(
        total_records=stats["total_records"],
        compliant_count=stats["compliant_count"],
        non_compliant_count=stats["non_compliant_count"],
        warning_count=stats["warning_count"],
        compliance_rate=stats["compliance_rate"],
        latest_record=latest_record,
        average_pm25=stats["average_pm25"],
        average_pm10=stats["average_pm10"],
        max_pm25=stats["max_pm25"],
        max_pm10=stats["max_pm10"]
    )

