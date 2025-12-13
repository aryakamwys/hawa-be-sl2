from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.db.models.compliance import ComplianceRecord, ComplianceStatusEnum
from app.services.compliance.schemas import ComplianceRecordCreate
from app.services.weather.heatmap_processor import HeatmapProcessor
from app.services.weather.sheets_cache_service import get_cached_sheets_data


class ComplianceService:
    def __init__(self, db: Session) -> None:
        self.db = db
    
    def _calculate_compliance_status(
        self,
        emission_pm25: float,
        emission_pm10: float,
        threshold_pm25: float,
        threshold_pm10: float
    ) -> ComplianceStatusEnum:
        """Calculate compliance status based on emissions vs thresholds"""
        pm25_compliant = emission_pm25 <= threshold_pm25
        pm10_compliant = emission_pm10 <= threshold_pm10
        
        if pm25_compliant and pm10_compliant:
            return ComplianceStatusEnum.COMPLIANT
        elif not pm25_compliant or not pm10_compliant:
            # Check if close to threshold (within 10%)
            pm25_warning = emission_pm25 <= threshold_pm25 * 1.1
            pm10_warning = emission_pm10 <= threshold_pm10 * 1.1
            
            if (pm25_warning and pm10_compliant) or (pm25_compliant and pm10_warning):
                return ComplianceStatusEnum.WARNING
            else:
                return ComplianceStatusEnum.NON_COMPLIANT
        else:
            return ComplianceStatusEnum.NON_COMPLIANT
    
    def create_compliance_record(
        self,
        user_id: int,
        data: ComplianceRecordCreate
    ) -> ComplianceRecord:
        """Create a new compliance record"""
        compliance_status = self._calculate_compliance_status(
            emission_pm25=data.emission_pm25,
            emission_pm10=data.emission_pm10,
            threshold_pm25=data.regulatory_threshold_pm25,
            threshold_pm10=data.regulatory_threshold_pm10
        )
        
        record = ComplianceRecord(
            user_id=user_id,
            emission_pm25=data.emission_pm25,
            emission_pm10=data.emission_pm10,
            regulatory_threshold_pm25=data.regulatory_threshold_pm25,
            regulatory_threshold_pm10=data.regulatory_threshold_pm10,
            compliance_status=compliance_status,
            notes=data.notes,
            facility_name=data.facility_name,
            recorded_at=data.recorded_at or datetime.utcnow()
        )
        
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record
    
    def get_compliance_history(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        start_date: datetime | None = None,
        end_date: datetime | None = None
    ) -> list[ComplianceRecord]:
        """Get compliance history for a user"""
        query = self.db.query(ComplianceRecord).filter(
            ComplianceRecord.user_id == user_id
        )
        
        if start_date:
            query = query.filter(ComplianceRecord.recorded_at >= start_date)
        if end_date:
            query = query.filter(ComplianceRecord.recorded_at <= end_date)
        
        return query.order_by(ComplianceRecord.recorded_at.desc()).offset(offset).limit(limit).all()
    
    def generate_compliance_from_heatmap(
        self,
        user_id: int,
        regulatory_threshold_pm25: float = 35.0,  # Default WHO guideline
        regulatory_threshold_pm10: float = 50.0,  # Default WHO guideline
        location_filter: str | None = None
    ) -> list[ComplianceRecord]:
        """
        Auto-generate compliance records from heatmap data
        This creates compliance records based on real-time heatmap pollution data
        """
        heatmap_spreadsheet_id = "1p69Ae67JGlScrMlSDnebuZMghXYMY7IykiT1gQwello"
        
        try:
            raw_data = get_cached_sheets_data(
                spreadsheet_id=heatmap_spreadsheet_id,
                worksheet_name="Sheet1",
                force_refresh=True
            )
            
            heatmap_data = HeatmapProcessor.process_heatmap_points(
                raw_data=raw_data,
                spreadsheet_id=heatmap_spreadsheet_id,
                worksheet_name="Sheet1"
            )
            
            records = []
            for point in heatmap_data.get("points", []):
                # Filter by location if specified
                if location_filter and location_filter.lower() not in str(point.get("location", "")).lower():
                    continue
                
                pm25 = point.get("pm2_5")
                pm10 = point.get("pm10")
                location = point.get("location", "Unknown")
                
                if pm25 is None or pm10 is None:
                    continue
                
                compliance_status = self._calculate_compliance_status(
                    emission_pm25=pm25,
                    emission_pm10=pm10,
                    threshold_pm25=regulatory_threshold_pm25,
                    threshold_pm10=regulatory_threshold_pm10
                )
                
                # Check if record already exists for this location and timestamp
                existing = self.db.query(ComplianceRecord).filter(
                    and_(
                        ComplianceRecord.user_id == user_id,
                        ComplianceRecord.facility_name == location,
                        ComplianceRecord.recorded_at >= datetime.utcnow() - timedelta(hours=1)
                    )
                ).first()
                
                if not existing:
                    record = ComplianceRecord(
                        user_id=user_id,
                        emission_pm25=pm25,
                        emission_pm10=pm10,
                        regulatory_threshold_pm25=regulatory_threshold_pm25,
                        regulatory_threshold_pm10=regulatory_threshold_pm10,
                        compliance_status=compliance_status,
                        facility_name=location,
                        notes=f"Auto-generated from heatmap data",
                        recorded_at=datetime.utcnow()
                    )
                    self.db.add(record)
                    records.append(record)
            
            if records:
                self.db.commit()
                for record in records:
                    self.db.refresh(record)
            
            return records
            
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Failed to generate compliance from heatmap: {str(e)}")
    
    def get_compliance_stats(
        self,
        user_id: int,
        days: int = 30
    ) -> dict:
        """Get compliance statistics for a user"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        records = self.db.query(ComplianceRecord).filter(
            and_(
                ComplianceRecord.user_id == user_id,
                ComplianceRecord.recorded_at >= start_date
            )
        ).all()
        
        if not records:
            return {
                "total_records": 0,
                "compliant_count": 0,
                "non_compliant_count": 0,
                "warning_count": 0,
                "compliance_rate": 0.0,
                "latest_record": None,
                "average_pm25": None,
                "average_pm10": None,
                "max_pm25": None,
                "max_pm10": None
            }
        
        total = len(records)
        compliant = sum(1 for r in records if r.compliance_status == ComplianceStatusEnum.COMPLIANT)
        non_compliant = sum(1 for r in records if r.compliance_status == ComplianceStatusEnum.NON_COMPLIANT)
        warning = sum(1 for r in records if r.compliance_status == ComplianceStatusEnum.WARNING)
        
        compliance_rate = (compliant / total * 100) if total > 0 else 0.0
        
        avg_pm25 = sum(r.emission_pm25 for r in records) / total
        avg_pm10 = sum(r.emission_pm10 for r in records) / total
        max_pm25 = max(r.emission_pm25 for r in records)
        max_pm10 = max(r.emission_pm10 for r in records)
        
        latest = max(records, key=lambda r: r.recorded_at)
        
        return {
            "total_records": total,
            "compliant_count": compliant,
            "non_compliant_count": non_compliant,
            "warning_count": warning,
            "compliance_rate": round(compliance_rate, 2),
            "latest_record": latest,
            "average_pm25": round(avg_pm25, 2),
            "average_pm10": round(avg_pm10, 2),
            "max_pm25": round(max_pm25, 2),
            "max_pm10": round(max_pm10, 2)
        }

