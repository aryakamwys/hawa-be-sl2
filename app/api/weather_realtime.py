"""
Realtime Weather Warnings API
Endpoints for mapping warnings per column of latest data with personalized recommendations
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.exceptions import handle_google_sheets_error
from app.db.postgres import get_db
from app.services.weather.realtime_warning_service import RealtimeWarningService

if TYPE_CHECKING:
    from app.db.models.user import User

router = APIRouter(prefix="/weather/realtime", tags=["weather-realtime"])


@router.get("/warnings", status_code=status.HTTP_200_OK)
def get_realtime_warnings(
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db),
    spreadsheet_id: str = Query(..., description="Google Sheets ID"),
    worksheet_name: str = Query(default="Sheet1", description="Worksheet name"),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of last columns to process (default: 20, max: 100)"
    ),
    time_window_seconds: int = Query(
        default=60,
        ge=1,
        le=3600,
        description="Time window in seconds to filter data (default: 60, max: 3600)"
    )
):
    """
    Get realtime warnings based on last N columns from timestamp.
    Mapping per column for pollution spike detection with personalized recommendations.
    
    Only returns warnings with risk level medium or higher.
    
    **Request Parameters**:
    - `spreadsheet_id`: Google Sheets ID (required)
    - `worksheet_name`: Worksheet name (default: Sheet1)
    - `limit`: Number of last columns (default: 20, max: 100)
    - `time_window_seconds`: Time window in seconds (default: 60, max: 3600)
    
    **Response**:
    - List of warnings with complete metadata
    - Each warning contains: column_index, timestamp, location, PM values, risk level, recommendations
    """
    service = RealtimeWarningService(db)
    
    try:
        warnings = service.get_warnings_by_columns(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
            user=current_user,
            limit=limit,
            time_window_seconds=time_window_seconds
        )
        
        return {
            "success": True,
            "warnings": warnings,
            "total_warnings": len(warnings),
            "limit": limit,
            "time_window_seconds": time_window_seconds,
            "timestamp": datetime.now().isoformat()
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise handle_google_sheets_error(e)


@router.get("/warnings/summary", status_code=status.HTTP_200_OK)
def get_realtime_warnings_summary(
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db),
    spreadsheet_id: str = Query(..., description="Google Sheets ID"),
    worksheet_name: str = Query(default="Sheet1", description="Worksheet name"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of last columns"),
    time_window_seconds: int = Query(default=60, ge=1, le=3600, description="Time window in seconds")
):
    """
    Get summary statistics from realtime warnings.
    Useful for dashboard or overview.
    
    **Response**:
    - Total warnings
    - Risk level distribution
    - Locations affected
    - Average PM2.5 and PM10 values
    - Max PM2.5 and PM10 values
    """
    service = RealtimeWarningService(db)
    
    try:
        summary = service.get_warnings_summary(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
            user=current_user,
            limit=limit,
            time_window_seconds=time_window_seconds
        )
        
        return {
            "success": True,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise handle_google_sheets_error(e)






