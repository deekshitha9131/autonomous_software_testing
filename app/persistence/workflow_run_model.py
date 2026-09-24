from sqlalchemy import Column, String, Text, TIMESTAMP, func
from sqlalchemy.types import TypeDecorator, TEXT
from app.core.database import Base
import uuid
import json
from sqlalchemy.dialects.postgresql import JSONB


class JSONBType(TypeDecorator):
    """Use JSONB for PostgreSQL, JSON for SQLite."""
    impl = TEXT
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            # Default to JSON for SQLite and others
            return dialect.type_descriptor(TEXT)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == 'postgresql':
            # Let the JSONB type handle it
            return value
        else:
            # For SQLite and others, convert to JSON string
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == 'postgresql':
            return value
        else:
            # For SQLite and others, convert from JSON string
            return json.loads(value)


class WorkflowRun(Base):
    """SQLalchemy model for workflow run persistence."""
    __tablename__ = "workflow_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    requirement = Column(Text, nullable=False)
    status = Column(String(50))
    workflow_state = Column(JSONBType(), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())