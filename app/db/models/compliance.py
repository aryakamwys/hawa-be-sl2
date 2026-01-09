from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, DateTime, ForeignKey, Integer, Enum as SqlEnum
from sqlalchemy.sql import func
from app.db.postgres import Base


class ComplianceStatusEnum(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    WARNING = "warning"


class ComplianceRecord(Base):
    __tablename__ = "compliance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Emission data (actual measurements)
    emission_pm25: Mapped[float] = mapped_column(Float, nullable=False)
    emission_pm10: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Regulatory thresholds (standards that must be met)
    regulatory_threshold_pm25: Mapped[float] = mapped_column(Float, nullable=False)
    regulatory_threshold_pm10: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Compliance status (calculated)
    compliance_status: Mapped[ComplianceStatusEnum] = mapped_column(
        SqlEnum(ComplianceStatusEnum),
        nullable=False,
        default=ComplianceStatusEnum.COMPLIANT
    )
    
    # Additional metadata
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    facility_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # Timestamps
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="compliance_records")







