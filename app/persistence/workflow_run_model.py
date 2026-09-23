from sqlalchemy import Column, String, Text, TIMESTAMP, func, JSON
from app.core.database import Base
import uuid


class WorkflowRun(Base):
    """SQLalchemy model for workflow run persistence."""
    __tablename__ = "workflow_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    requirement = Column(Text, nullable=False)
    status = Column(String(50))
    workflow_state = Column(JSON, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())