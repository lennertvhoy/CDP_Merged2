"""CDP 360 Data Model - Domain models for PostgreSQL canonical store.

This module defines SQLAlchemy models for the customer intelligence layer,
following the privacy-by-design architecture where:
- Source systems hold PII and operational master records
- PostgreSQL holds customer intelligence, analytics, and derived facts
- Tracardi holds projected activation runtime state
"""

from src.models.ai_decisions import AIDecision
from src.models.audit import AuditLog
from src.models.base import Base, TimestampMixin, UIDMixin
from src.models.consent import ConsentEvent, PIIResolutionAudit
from src.models.contact import ContactRole
from src.models.database import (
    DatabaseManager,
    db_session_scope,
    get_db_session,
    init_database,
)
from src.models.events import EventFact
from src.models.identity import IdentityMergeEvent, SourceIdentityLink
from src.models.organization import Organization
from src.models.projection import ActivationProjectionState
from src.models.segments import SegmentDefinition, SegmentMembership
from src.models.traits import ProfileTrait

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UIDMixin",
    # Core Entities
    "Organization",
    "SourceIdentityLink",
    "IdentityMergeEvent",
    "ContactRole",
    # Events & Traits
    "EventFact",
    "ProfileTrait",
    # AI & Intelligence
    "AIDecision",
    # Consent & Privacy
    "ConsentEvent",
    "PIIResolutionAudit",
    # Segments
    "SegmentDefinition",
    "SegmentMembership",
    # Projection & Sync
    "ActivationProjectionState",
    # Audit
    "AuditLog",
    # Database
    "DatabaseManager",
    "init_database",
    "get_db_session",
    "db_session_scope",
]
