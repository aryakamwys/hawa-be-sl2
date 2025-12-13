from datetime import datetime
from pydantic import BaseModel, Field
from app.db.models.compliance import ComplianceStatusEnum


class ComplianceRecordCreate(BaseModel):
    emission_pm25: float = Field(..., gt=0, description="PM2.5 emission value (μg/m³)")
    emission_pm10: float = Field(..., gt=0, description="PM10 emission value (μg/m³)")
    regulatory_threshold_pm25: float = Field(..., gt=0, description="Regulatory threshold for PM2.5 (μg/m³)")
    regulatory_threshold_pm10: float = Field(..., gt=0, description="Regulatory threshold for PM10 (μg/m³)")
    notes: str | None = Field(None, max_length=500, description="Optional notes")
    facility_name: str | None = Field(None, max_length=200, description="Facility or location name")
    recorded_at: datetime | None = Field(None, description="Record timestamp (defaults to now)")


class ComplianceRecordResponse(BaseModel):
    id: int
    user_id: int
    emission_pm25: float
    emission_pm10: float
    regulatory_threshold_pm25: float
    regulatory_threshold_pm10: float
    compliance_status: str
    notes: str | None
    facility_name: str | None
    recorded_at: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ComplianceStatsResponse(BaseModel):
    total_records: int
    compliant_count: int
    non_compliant_count: int
    warning_count: int
    compliance_rate: float
    latest_record: ComplianceRecordResponse | None
    average_pm25: float | None
    average_pm10: float | None
    max_pm25: float | None
    max_pm10: float | None






