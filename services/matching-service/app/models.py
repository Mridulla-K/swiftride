import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from shared.database import Base

class MatchStatus(str, Enum):
    matched = "matched"
    reassigned = "reassigned"
    failed = "failed"

class Match(Base):
    __tablename__ = "matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ride_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    driver_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    matched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="matched")
