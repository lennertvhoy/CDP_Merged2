"""
Search Engine for CDP_Merged.
From CDPT - Query builder architecture with TQL/SQL/ES support.
"""

from pydantic import BaseModel, Field


class ProfileSearchParams(BaseModel):
    """
    Intermediate Representation (IR) for search parameters.
    Decouples AI intent from specific database query language.
    """

    keywords: str | None = Field(
        None, description="Partial name of the company or general keyword."
    )
    enterprise_number: str | None = Field(
        None, description="Enterprise number (e.g., '0207.446.759' or '0207446759')."
    )
    nace_codes: list[str] | None = Field(
        None, description="List of NACE codes (e.g., ['62010']) found via lookup tool."
    )
    nace_code: str | None = Field(
        None,
        description="Single NACE code convenience alias (e.g., '62010'). Normalized to nace_codes.",
    )
    juridical_codes: list[str] | None = Field(
        None, description="List of Juridical form codes (e.g., ['014']) found via lookup tool."
    )
    juridical_keyword: str | None = Field(
        None,
        description="Juridical form keyword (e.g., 'BV', 'NV', 'VZW'). Resolves automatically.",
    )
    city: str | None = Field(None, description="City name (e.g., 'Gent').")
    zip_code: str | None = Field(None, description="Zip code (e.g., '9000').")
    status: str | None = Field(
        None,
        description=(
            "Status code such as 'AC' for active companies. Leave empty/None unless the user "
            "explicitly asks for active, inactive, or all statuses."
        ),
    )
    min_start_date: str | None = Field(
        None, description="Filter for companies started after this date (YYYY-MM-DD)."
    )
    has_phone: bool | None = Field(
        False, description="If True, only return profiles with a phone number."
    )
    has_email: bool | None = Field(
        False, description="If True, only return profiles with an email address."
    )
    email_domain: str | None = Field(
        None,
        description="Restrict results to a specific email domain (e.g., 'gmail.com').",
    )
