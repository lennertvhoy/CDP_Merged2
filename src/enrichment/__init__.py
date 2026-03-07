"""
Data Enrichment Module for Tracardi Profiles.

Provides enrichment capabilities for 516K+ profiles:
- Geocoding via OpenStreetMap/Nominatim
- AI-generated company descriptions via Azure OpenAI
- Website discovery via pattern matching
- CBE Open Data cross-reference
- Contact validation (email/phone)
"""

from src.enrichment.cbe_integration import CBEIntegrationEnricher
from src.enrichment.contact_validation import ContactValidationEnricher
from src.enrichment.deduplication import DeduplicationEnricher
from src.enrichment.descriptions import DescriptionEnricher
from src.enrichment.geocoding import GeocodingEnricher
from src.enrichment.progress import CostTracker, ProgressTracker
from src.enrichment.website_discovery import WebsiteDiscoveryEnricher

__all__ = [
    "GeocodingEnricher",
    "DeduplicationEnricher",
    "DescriptionEnricher",
    "WebsiteDiscoveryEnricher",
    "CBEIntegrationEnricher",
    "ContactValidationEnricher",
    "ProgressTracker",
    "CostTracker",
]
