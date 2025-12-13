"""
Realtime Warning Service
Service for mapping warnings per column of latest data with personalized recommendations
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.services.weather.sheets_cache_service import get_realtime_sheets_data
from app.services.weather.spreadsheet_service import SpreadsheetService
from app.services.weather.recommendation_service import WeatherRecommendationService


class RealtimeWarningService:
    """
    Service to generate realtime warnings based on latest IoT data.
    Mapping per column (default: last 20 columns) with personalized recommendations.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.sheet_service = SpreadsheetService()
        self.recommendation_service = WeatherRecommendationService(db)
    
    def get_warnings_by_columns(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        user: User,
        limit: int = 20,
        time_window_seconds: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Get warnings per column (last limit) with realtime mapping
        
        Args:
            spreadsheet_id: Google Sheets ID
            worksheet_name: Worksheet name
            user: User object for personalization
            limit: Number of last columns to process (default: 20)
            time_window_seconds: Time window in seconds to filter data (default: 60)
        
        Returns:
            List of warnings with complete metadata
        """
        # Get latest data with 1 second cache
        raw_data = get_realtime_sheets_data(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
            force_refresh=False
        )
        
        if not raw_data:
            return []
        
        # Get last N columns
        recent_data = raw_data[-limit:] if len(raw_data) > limit else raw_data
        
        warnings = []
        now = datetime.now()
        
        for idx, row in enumerate(recent_data):
            try:
                # Process data
                processed = self.sheet_service.process_bmkg_data(row)
                
                # Check if within time window
                timestamp_str = processed.get('timestamp')
                if timestamp_str:
                    try:
                        # Try parsing timestamp
                        if isinstance(timestamp_str, str):
                            # Try multiple formats
                            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S"):
                                try:
                                    row_time = datetime.strptime(timestamp_str, fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                # Try ISO format
                                try:
                                    row_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                except:
                                    row_time = None
                        else:
                            row_time = timestamp_str
                        
                        if row_time:
                            # Remove timezone info for comparison
                            if row_time.tzinfo:
                                row_time = row_time.replace(tzinfo=None)
                            
                            time_diff = (now - row_time).total_seconds()
                            
                            # Skip if outside window
                            if time_diff > time_window_seconds or time_diff < 0:
                                continue
                    except Exception:
                        # If parsing fails, still process (might be different format)
                        pass
                
                # Generate recommendation for this column
                recommendation = self.recommendation_service.get_personalized_recommendation(
                    user=user,
                    weather_data=processed
                )
                
                risk_level = recommendation.get('risk_level', 'low')
                
                # Only return warning if risk is medium or higher
                if risk_level in ['medium', 'high', 'critical']:
                    # Calculate column index (1-based, from end)
                    column_index = len(raw_data) - len(recent_data) + idx + 1
                    
                    warnings.append({
                        "column_index": column_index,
                        "timestamp": processed.get('timestamp'),
                        "location": processed.get('location', 'Unknown'),
                        "pm25": processed.get('pm25'),
                        "pm10": processed.get('pm10'),
                        "temperature": processed.get('temperature'),
                        "humidity": processed.get('humidity'),
                        "risk_level": risk_level,
                        "aqi_level": recommendation.get('aqi_level', 'unknown'),
                        "warning_message": recommendation.get('primary_concern', ''),
                        "summary": recommendation.get('summary', ''),
                        "recommendations": recommendation.get('recommendations', [])[:3],  # Top 3
                        "personalized_advice": recommendation.get('personalized_advice', ''),
                        "tips": recommendation.get('tips', [])[:3]  # Top 3 tips
                    })
            except Exception as e:
                # Log error but continue processing other columns
                print(f"Error processing column {idx}: {e}")
                continue
        
        # Sort by column_index (ascending)
        warnings.sort(key=lambda x: x.get('column_index', 0))
        
        return warnings
    
    def get_warnings_summary(
        self,
        spreadsheet_id: str,
        worksheet_name: str,
        user: User,
        limit: int = 20,
        time_window_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Get summary of warnings (statistics and overview)
        
        Returns:
            Dictionary with summary statistics
        """
        warnings = self.get_warnings_by_columns(
            spreadsheet_id=spreadsheet_id,
            worksheet_name=worksheet_name,
            user=user,
            limit=limit,
            time_window_seconds=time_window_seconds
        )
        
        if not warnings:
            return {
                "total_warnings": 0,
                "risk_levels": {},
                "locations": [],
                "avg_pm25": None,
                "avg_pm10": None
            }
        
        # Calculate statistics
        risk_levels = {}
        locations = []
        pm25_values = []
        pm10_values = []
        
        for warning in warnings:
            risk = warning.get('risk_level', 'unknown')
            risk_levels[risk] = risk_levels.get(risk, 0) + 1
            
            location = warning.get('location')
            if location and location not in locations:
                locations.append(location)
            
            if warning.get('pm25') is not None:
                pm25_values.append(warning['pm25'])
            if warning.get('pm10') is not None:
                pm10_values.append(warning['pm10'])
        
        return {
            "total_warnings": len(warnings),
            "risk_levels": risk_levels,
            "locations": locations,
            "avg_pm25": sum(pm25_values) / len(pm25_values) if pm25_values else None,
            "avg_pm10": sum(pm10_values) / len(pm10_values) if pm10_values else None,
            "max_pm25": max(pm25_values) if pm25_values else None,
            "max_pm10": max(pm10_values) if pm10_values else None
        }





