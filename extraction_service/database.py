"""Database models and operations using SQLAlchemy."""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    create_engine,
    Index,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from config import settings

Base = declarative_base()


class Requirement(Base):
    """Requirement model - stores normalized regulatory requirements."""
    
    __tablename__ = "requirements"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    update_id = Column(String(50), unique=True, nullable=False)
    published_date = Column(Date, nullable=False)
    source = Column(String(100), nullable=False)
    source_url = Column(Text, nullable=False)
    celex = Column(String(50), nullable=True)
    consolidation_date = Column(Date, nullable=True)
    access_timestamp = Column(DateTime, nullable=False)
    regulation_family = Column(String(50), nullable=False)
    reference = Column(Text, nullable=True)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    change_type = Column(String(20), nullable=False)
    effective_date = Column(Date, nullable=True)
    deadline_date = Column(Date, nullable=True)
    severity = Column(String(20), nullable=False)
    action_required = Column(Text, nullable=True)
    scope = Column(Text, nullable=False)  # JSON stored as TEXT
    corrects = Column(String(50), nullable=True)
    content_hash = Column(String(64), nullable=True)  # SHA-256 hash for deduplication
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("idx_requirements_family", "regulation_family"),
        Index("idx_requirements_deadline", "deadline_date"),
        Index("idx_requirements_celex", "celex"),
        Index("idx_requirements_severity", "severity"),
        Index("idx_requirements_hash", "content_hash"),
    )
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            "update_id": self.update_id,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "source": self.source,
            "source_url": self.source_url,
            "celex": self.celex,
            "consolidation_date": self.consolidation_date.isoformat() if self.consolidation_date else None,
            "access_timestamp": self.access_timestamp.isoformat() if self.access_timestamp else None,
            "regulation_family": self.regulation_family,
            "reference": self.reference,
            "title": self.title,
            "summary": self.summary,
            "change_type": self.change_type,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "deadline_date": self.deadline_date.isoformat() if self.deadline_date else None,
            "severity": self.severity,
            "action_required": self.action_required,
            "scope": json.loads(self.scope) if isinstance(self.scope, str) else self.scope,
            "corrects": self.corrects,
        }


class ExtractionRun(Base):
    """ExtractionRun model - audit trail for extraction jobs."""
    
    __tablename__ = "extraction_runs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)  # running, completed, failed
    requirements_found = Column(Integer, default=0)
    requirements_new = Column(Integer, default=0)
    requirements_updated = Column(Integer, default=0)
    cursor_timestamp = Column(DateTime, nullable=True)  # Last modification timestamp processed
    error_message = Column(Text, nullable=True)
    
    __table_args__ = (
        Index("idx_extraction_runs_status", "status"),
        Index("idx_extraction_runs_started", "started_at"),
    )


# Database engine and session
engine = None
SessionLocal = None


def init_db():
    """Initialize database engine and session."""
    global engine, SessionLocal
    
    # Create engine
    if settings.database_url.startswith("sqlite"):
        # SQLite-specific settings
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # PostgreSQL settings
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    
    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Get database session."""
    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """Get database session (non-generator version)."""
    if SessionLocal is None:
        init_db()
    return SessionLocal()


# CRUD operations for Requirements

def insert_requirement(db: Session, requirement_data: dict, content_hash: str) -> Requirement:
    """Insert a new requirement."""
    # Convert scope dict to JSON string
    if isinstance(requirement_data.get("scope"), dict):
        requirement_data["scope"] = json.dumps(requirement_data["scope"])
    
    requirement = Requirement(
        **requirement_data,
        content_hash=content_hash,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


def update_requirement(db: Session, requirement_id: int, requirement_data: dict, content_hash: str) -> Requirement:
    """Update an existing requirement."""
    requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
    if not requirement:
        raise ValueError(f"Requirement with id {requirement_id} not found")
    
    # Convert scope dict to JSON string
    if isinstance(requirement_data.get("scope"), dict):
        requirement_data["scope"] = json.dumps(requirement_data["scope"])
    
    for key, value in requirement_data.items():
        setattr(requirement, key, value)
    
    requirement.content_hash = content_hash
    requirement.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(requirement)
    return requirement


def get_requirement_by_hash(db: Session, content_hash: str) -> Optional[Requirement]:
    """Get requirement by content hash for deduplication."""
    return db.query(Requirement).filter(Requirement.content_hash == content_hash).first()


def get_requirement_by_update_id(db: Session, update_id: str) -> Optional[Requirement]:
    """Get requirement by update_id."""
    return db.query(Requirement).filter(Requirement.update_id == update_id).first()


def list_requirements(
    db: Session,
    regulation_family: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Requirement]:
    """List requirements with optional filters and pagination."""
    query = db.query(Requirement)
    
    if regulation_family:
        query = query.filter(Requirement.regulation_family == regulation_family)
    
    if severity:
        query = query.filter(Requirement.severity == severity)
    
    # Sort by deadline_date ascending (earliest first)
    query = query.order_by(Requirement.deadline_date.asc())
    
    return query.limit(limit).offset(offset).all()


def count_requirements(
    db: Session,
    regulation_family: Optional[str] = None,
    severity: Optional[str] = None,
) -> int:
    """Count requirements with optional filters."""
    query = db.query(Requirement)
    
    if regulation_family:
        query = query.filter(Requirement.regulation_family == regulation_family)
    
    if severity:
        query = query.filter(Requirement.severity == severity)
    
    return query.count()


# CRUD operations for ExtractionRuns

def start_extraction_run(db: Session) -> ExtractionRun:
    """Start a new extraction run."""
    run = ExtractionRun(
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def complete_extraction_run(
    db: Session,
    run_id: int,
    requirements_found: int,
    requirements_new: int,
    requirements_updated: int,
    cursor_timestamp: Optional[datetime] = None,
) -> ExtractionRun:
    """Mark extraction run as completed."""
    run = db.query(ExtractionRun).filter(ExtractionRun.id == run_id).first()
    if not run:
        raise ValueError(f"ExtractionRun with id {run_id} not found")
    
    run.completed_at = datetime.now(timezone.utc)
    run.status = "completed"
    run.requirements_found = requirements_found
    run.requirements_new = requirements_new
    run.requirements_updated = requirements_updated
    run.cursor_timestamp = cursor_timestamp
    
    db.commit()
    db.refresh(run)
    return run


def fail_extraction_run(db: Session, run_id: int, error_message: str) -> ExtractionRun:
    """Mark extraction run as failed."""
    run = db.query(ExtractionRun).filter(ExtractionRun.id == run_id).first()
    if not run:
        raise ValueError(f"ExtractionRun with id {run_id} not found")
    
    run.completed_at = datetime.now(timezone.utc)
    run.status = "failed"
    run.error_message = error_message
    
    db.commit()
    db.refresh(run)
    return run


def get_last_cursor(db: Session) -> Optional[datetime]:
    """Get the last successful cursor timestamp."""
    run = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.status == "completed")
        .filter(ExtractionRun.cursor_timestamp.isnot(None))
        .order_by(ExtractionRun.started_at.desc())
        .first()
    )
    return run.cursor_timestamp if run else None


def check_db_health(db: Session) -> bool:
    """Check database connectivity."""
    try:
        db.execute("SELECT 1")
        return True
    except Exception:
        return False
