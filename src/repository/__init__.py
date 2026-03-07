"""Repository layer for CDP 360 Data Model.

This module provides repository/DAO pattern for accessing 360 Data Model entities.
Repositories abstract database operations and provide a clean interface for
business logic layers.
"""

from src.repository.base import BaseRepository
from src.repository.organization import OrganizationRepository

__all__ = [
    "BaseRepository",
    "OrganizationRepository",
]
