"""AI Interface Tools - Backward Compatibility Wrapper.

This module re-exports all tools from the new submodule structure.
New code should import from src.ai_interface.tools submodule directly.

DEPRECATED: Import directly from src.ai_interface.tools submodule instead.
  - from src.ai_interface.tools.search import search_profiles
  - from src.ai_interface.tools.email import send_email_via_resend
  - etc.
"""

# Re-export all tools for backward compatibility
from src.ai_interface.tools import (
    aggregate_profiles,
    create_segment,
    email_segment_export,
    export_segment_to_csv,
    get_segment_stats,
    lookup_juridical_code,
    lookup_nace_code,
    push_segment_to_resend,
    push_to_flexmail,
    search_profiles,
    send_bulk_emails_via_resend,
    send_campaign_via_resend,
    send_email_via_resend,
)

# Also re-export from submodules for direct access
from src.ai_interface.tools.nace_resolver import (
    DOMAIN_CODE_PREFIX_FILTERS,
    DOMAIN_HINT_CODES,
    DOMAIN_SYNONYMS,
    GENERIC_ACTIVITY_TERMS,
    JURIDICAL_CODES,
    NACE_CATALOG,
    NACE_CODES,
)

__all__ = [
    # Search
    "search_profiles",
    "create_segment",
    "get_segment_stats",
    "aggregate_profiles",
    # NACE/Juridical
    "lookup_nace_code",
    "lookup_juridical_code",
    # Email
    "push_to_flexmail",
    "send_email_via_resend",
    "send_bulk_emails_via_resend",
    "push_segment_to_resend",
    "send_campaign_via_resend",
    # Export
    "export_segment_to_csv",
    "email_segment_export",
    # Constants (for backward compatibility)
    "NACE_CODES",
    "JURIDICAL_CODES",
    "NACE_CATALOG",
    "DOMAIN_SYNONYMS",
    "DOMAIN_HINT_CODES",
    "DOMAIN_CODE_PREFIX_FILTERS",
    "GENERIC_ACTIVITY_TERMS",
]
