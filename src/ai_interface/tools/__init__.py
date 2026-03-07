"""AI Interface Tools - Re-exported for backward compatibility.

This module provides a unified interface to all AI tools.
New code should import from the specific submodule directly when possible.
"""

# Search tools
# Email marketing tools
from src.ai_interface.tools.artifact import create_data_artifact
from src.ai_interface.tools.email import (
    push_segment_to_resend,
    push_to_flexmail,
    send_bulk_emails_via_resend,
    send_campaign_via_resend,
    send_email_via_resend,
)

# Export tools
from src.ai_interface.tools.export import (
    email_segment_export,
    export_segment_to_csv,
)

# NACE/Juridical resolution tools
from src.ai_interface.tools.nace_resolver import (
    lookup_juridical_code,
    lookup_nace_code,
)
from src.ai_interface.tools.search import (
    aggregate_profiles,
    create_segment,
    get_data_coverage_stats,
    get_segment_stats,
    search_profiles,
)

# Unified 360° View tools
from src.ai_interface.tools.unified_360 import (
    find_high_value_accounts,
    get_geographic_revenue_distribution,
    get_identity_link_quality,
    get_industry_summary,
    query_unified_360,
)

__all__ = [
    "create_data_artifact",
    # Search
    "search_profiles",
    "create_segment",
    "get_segment_stats",
    "aggregate_profiles",
    "get_data_coverage_stats",
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
    # Unified 360° Views
    "query_unified_360",
    "get_industry_summary",
    "find_high_value_accounts",
    "get_geographic_revenue_distribution",
    "get_identity_link_quality",
]
