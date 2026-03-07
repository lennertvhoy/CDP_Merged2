"""
CBE Extended Client for financial data integration.

Fetches revenue, employee count, and founding date from CBE Open Data.
Data source: https://datastore.brussels/dataset/cbe
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.core.logger import get_logger

logger = get_logger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)


class CBEExtendedClient:
    """
    Client for fetching extended CBE data including financials.

    Uses CBE Open Data extended dataset which includes:
    - Annual accounts with revenue data
    - Employee count information
    - Founding/establishment dates
    """

    # CBE Open Data store URLs
    CBE_DATASTORE_BASE = "https://datastore.brussels/dataset/cbe"
    CBE_API_BASE = "https://kbopub.economie.fgov.be/kbo-open-data/api/v1"

    # Local data cache paths
    DEFAULT_DATA_DIR = "./data/cbe_extended"

    def __init__(
        self,
        data_dir: str | None = None,
        use_api: bool = True,
        cache_ttl_hours: int = 24,
    ):
        self.data_dir = Path(data_dir) if data_dir else Path(self.DEFAULT_DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.use_api = use_api
        self.cache_ttl_hours = cache_ttl_hours
        self._financials_cache: dict = {}
        self._employees_cache: dict = {}
        self._founding_dates_cache: dict = {}

        # Load any cached data
        self._load_cached_data()

    def _load_cached_data(self) -> None:
        """Load cached data from disk."""
        cache_file = self.data_dir / "cbe_extended_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self._financials_cache = data.get("financials", {})
                    self._employees_cache = data.get("employees", {})
                    self._founding_dates_cache = data.get("founding_dates", {})
                logger.info("cbe_extended_cache_loaded", entries=len(self._financials_cache))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("cbe_extended_cache_load_failed", error=str(e))

    def _save_cached_data(self) -> None:
        """Save cached data to disk."""
        cache_file = self.data_dir / "cbe_extended_cache.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "financials": self._financials_cache,
                        "employees": self._employees_cache,
                        "founding_dates": self._founding_dates_cache,
                        "last_updated": datetime.now(UTC).isoformat(),
                    },
                    f,
                    indent=2,
                    default=str,
                )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("cbe_extended_cache_save_failed", error=str(e))

    def _normalize_kbo(self, kbo_number: str) -> str:
        """Normalize KBO number to standard 10-digit format."""
        digits = "".join(c for c in kbo_number if c.isdigit())

        # Belgian KBO numbers are 10 digits
        if len(digits) == 9:
            digits = "0" + digits

        return digits

    def _format_kbo_for_lookup(self, kbo_number: str) -> str:
        """Format KBO as XXXX.XXX.XXX for API lookups."""
        normalized = self._normalize_kbo(kbo_number)
        return f"{normalized[:4]}.{normalized[4:7]}.{normalized[7:]}"

    @_retry
    async def fetch_enterprise_details(self, kbo_number: str) -> dict | None:
        """
        Fetch enterprise details from CBE API.

        Args:
            kbo_number: KBO enterprise number

        Returns:
            Enterprise details dict or None
        """
        if not self.use_api:
            return None

        normalized = self._normalize_kbo(kbo_number)
        cache_key = f"enterprise_{normalized}"

        # Check cache
        if cache_key in self._financials_cache:
            cached = self._financials_cache[cache_key]
            if self._is_cache_fresh(cached.get("cached_at")):
                return cached.get("data")

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.CBE_API_BASE}/enterprise/{normalized}"
                response = await client.get(url, timeout=15.0)

                if response.status_code == 200:
                    data = response.json()
                    self._financials_cache[cache_key] = {
                        "cached_at": datetime.now(UTC).isoformat(),
                        "data": data,
                    }
                    self._save_cached_data()
                    return data
                elif response.status_code == 404:
                    logger.debug("cbe_enterprise_not_found", kbo=normalized)
                else:
                    logger.warning("cbe_api_error", status=response.status_code, kbo=normalized)
                    response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.debug(
                "cbe_api_fetch_http_error", kbo=normalized, status_code=e.response.status_code
            )
            raise
        except httpx.RequestError as e:
            logger.debug("cbe_api_fetch_request_error", kbo=normalized, error=str(e))
            raise

        return None

    @_retry
    async def fetch_annual_accounts(self, kbo_number: str) -> dict | None:
        """
        Fetch annual accounts data for revenue information.

        Args:
            kbo_number: KBO enterprise number

        Returns:
            Annual accounts data with revenue or None
        """
        if not self.use_api:
            return None

        normalized = self._normalize_kbo(kbo_number)
        cache_key = f"accounts_{normalized}"

        # Check cache
        if cache_key in self._financials_cache:
            cached = self._financials_cache[cache_key]
            if self._is_cache_fresh(cached.get("cached_at")):
                return cached.get("data")

        try:
            async with httpx.AsyncClient() as client:
                # Try to fetch annual accounts from CBE
                url = f"{self.CBE_API_BASE}/enterprise/{normalized}/annual-accounts"
                response = await client.get(url, timeout=15.0)

                if response.status_code == 200:
                    data = response.json()
                    self._financials_cache[cache_key] = {
                        "cached_at": datetime.now(UTC).isoformat(),
                        "data": data,
                    }
                    self._save_cached_data()
                    return data
                elif response.status_code == 404:
                    logger.debug("cbe_accounts_not_found", kbo=normalized)
                else:
                    logger.warning(
                        "cbe_accounts_api_error", status=response.status_code, kbo=normalized
                    )
                    response.raise_for_status()

        except httpx.HTTPStatusError as e:
            logger.debug(
                "cbe_accounts_fetch_http_error", kbo=normalized, status_code=e.response.status_code
            )
            raise
        except httpx.RequestError as e:
            logger.debug("cbe_accounts_fetch_request_error", kbo=normalized, error=str(e))
            raise

        return None

    def _is_cache_fresh(self, cached_at: str | None) -> bool:
        """Check if cached data is still fresh."""
        if not cached_at:
            return False
        try:
            cache_time = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
            age_hours = (
                datetime.now(UTC) - cache_time.replace(tzinfo=None)
            ).total_seconds() / 3600
            return age_hours < self.cache_ttl_hours
        except (ValueError, TypeError):
            return False

    def get_revenue(self, kbo_number: str) -> dict | None:
        """
        Get revenue data for a company.

        Args:
            kbo_number: KBO enterprise number

        Returns:
            Dict with revenue info or None:
            {
                'revenue_eur': float,
                'revenue_year': int,
                'source': str,
                'confidence': str  # 'high', 'medium', 'low'
            }
        """
        normalized = self._normalize_kbo(kbo_number)

        # Check cache first
        cache_key = f"revenue_{normalized}"
        if cache_key in self._financials_cache:
            cached = self._financials_cache[cache_key]
            return cached.get("data")

        # Try to extract from cached annual accounts
        accounts_key = f"accounts_{normalized}"
        if accounts_key in self._financials_cache:
            accounts = self._financials_cache[accounts_key].get("data", {})
            revenue_data = self._extract_revenue_from_accounts(accounts)
            if revenue_data:
                self._financials_cache[cache_key] = {
                    "cached_at": datetime.now(UTC).isoformat(),
                    "data": revenue_data,
                }
                self._save_cached_data()
                return revenue_data

        return None

    def _extract_revenue_from_accounts(self, accounts: dict) -> dict | None:
        """Extract revenue from annual accounts data."""
        try:
            # Look for latest annual account with revenue
            if isinstance(accounts, list) and accounts:
                # Sort by year descending
                sorted_accounts = sorted(
                    accounts, key=lambda x: x.get("accountingYear", 0), reverse=True
                )

                for account in sorted_accounts:
                    revenue = (
                        account.get("turnover") or account.get("revenue") or account.get("sales")
                    )
                    if revenue:
                        year = account.get("accountingYear") or account.get("year")
                        return {
                            "revenue_eur": float(revenue),
                            "revenue_year": year,
                            "source": "cbe_annual_accounts",
                            "confidence": "high" if year and year >= 2022 else "medium",
                        }

            # Try nested structure
            if isinstance(accounts, dict):
                revenue = (
                    accounts.get("turnover") or accounts.get("revenue") or accounts.get("sales")
                )
                if revenue:
                    return {
                        "revenue_eur": float(revenue),
                        "revenue_year": accounts.get("accountingYear") or accounts.get("year"),
                        "source": "cbe_annual_accounts",
                        "confidence": "high",
                    }
        except Exception as e:
            logger.debug("revenue_extraction_failed", error=str(e))

        return None

    def get_employee_count(self, kbo_number: str) -> dict | None:
        """
        Get employee count for a company.

        Args:
            kbo_number: KBO enterprise number

        Returns:
            Dict with employee info or None:
            {
                'employees': int,
                'employee_range': str,  # '1-10', '10-49', '50-249', '250+'
                'year': int,
                'source': str,
                'confidence': str
            }
        """
        normalized = self._normalize_kbo(kbo_number)

        # Check cache first
        cache_key = f"employees_{normalized}"
        if cache_key in self._employees_cache:
            cached = self._employees_cache[cache_key]
            return cached.get("data")

        # Try to extract from cached enterprise data
        enterprise_key = f"enterprise_{normalized}"
        if enterprise_key in self._financials_cache:
            enterprise = self._financials_cache[enterprise_key].get("data", {})
            employee_data = self._extract_employees_from_enterprise(enterprise)
            if employee_data:
                self._employees_cache[cache_key] = {
                    "cached_at": datetime.now(UTC).isoformat(),
                    "data": employee_data,
                }
                self._save_cached_data()
                return employee_data

        return None

    def _extract_employees_from_enterprise(self, enterprise: dict) -> dict | None:
        """Extract employee count from enterprise data."""
        try:
            # Look for employee data in various fields
            employees = None

            # Try direct fields
            employees = enterprise.get("numberOfEmployees") or enterprise.get("employees")

            # Try nested structure
            if not employees and "workforce" in enterprise:
                workforce = enterprise["workforce"]
                if isinstance(workforce, dict):
                    employees = workforce.get("number") or workforce.get("count")
                elif isinstance(workforce, list) and workforce:
                    # Get most recent
                    latest = max(workforce, key=lambda x: x.get("year", 0))
                    employees = latest.get("number") or latest.get("count")

            if employees:
                emp_int = int(employees)
                return {
                    "employees": emp_int,
                    "employee_range": self._categorize_company_size(emp_int),
                    "year": enterprise.get("year") or enterprise.get("accountingYear"),
                    "source": "cbe_enterprise_data",
                    "confidence": "medium",
                }
        except Exception as e:
            logger.debug("employee_extraction_failed", error=str(e))

        return None

    def _categorize_company_size(self, employees: int) -> str:
        """
        Categorize company size based on employee count.

        Categories:
        - micro: < 10 employees
        - small: 10-49 employees
        - medium: 50-249 employees
        - large: 250+ employees
        """
        if employees < 10:
            return "micro"
        elif employees < 50:
            return "small"
        elif employees < 250:
            return "medium"
        else:
            return "large"

    def get_founding_date(self, kbo_number: str) -> dict | None:
        """
        Get founding date for a company.

        Args:
            kbo_number: KBO enterprise number

        Returns:
            Dict with founding info or None:
            {
                'founding_date': str,  # ISO format
                'founding_year': int,
                'company_age': int,  # years since founding
                'source': str,
                'confidence': str
            }
        """
        normalized = self._normalize_kbo(kbo_number)

        # Check cache first
        cache_key = f"founding_{normalized}"
        if cache_key in self._founding_dates_cache:
            cached = self._founding_dates_cache[cache_key]
            return cached.get("data")

        # Try to extract from cached enterprise data
        enterprise_key = f"enterprise_{normalized}"
        if enterprise_key in self._financials_cache:
            enterprise = self._financials_cache[enterprise_key].get("data", {})
            founding_data = self._extract_founding_from_enterprise(enterprise)
            if founding_data:
                self._founding_dates_cache[cache_key] = {
                    "cached_at": datetime.now(UTC).isoformat(),
                    "data": founding_data,
                }
                self._save_cached_data()
                return founding_data

        return None

    def _extract_founding_from_enterprise(self, enterprise: dict) -> dict | None:
        """Extract founding date from enterprise data."""
        try:
            # Look for start/founding date
            start_date = None

            # Try various field names
            start_date = enterprise.get("startDate") or enterprise.get("foundingDate")
            start_date = start_date or enterprise.get("establishmentDate")
            start_date = start_date or enterprise.get("registrationDate")

            # Try nested establishment
            if not start_date and "establishment" in enterprise:
                establishment = enterprise["establishment"]
                if isinstance(establishment, dict):
                    start_date = establishment.get("startDate") or establishment.get("date")

            if start_date:
                # Parse date
                parsed_date = self._parse_date(start_date)
                if parsed_date:
                    founding_year = parsed_date.year
                    company_age = datetime.now(UTC).year - founding_year

                    return {
                        "founding_date": parsed_date.isoformat(),
                        "founding_year": founding_year,
                        "company_age": company_age,
                        "source": "cbe_enterprise_data",
                        "confidence": "high",
                    }
        except Exception as e:
            logger.debug("founding_date_extraction_failed", error=str(e))

        return None

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse date from various formats."""
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%Y%m%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Try ISO format
        try:
            return datetime.fromisoformat(
                date_str.replace("Z", "+00:00").replace("T", " ").split(".")[0]
            )
        except Exception:
            pass

        return None

    async def get_company_financials(self, kbo_number: str) -> dict:
        """
        Get complete financial overview for a company.

        Args:
            kbo_number: KBO enterprise number

        Returns:
            Dict with all available financial data
        """
        normalized = self._normalize_kbo(kbo_number)

        # Fetch fresh data if needed
        if self.use_api:
            try:
                await self.fetch_enterprise_details(kbo_number)
                await self.fetch_annual_accounts(kbo_number)
            except Exception as exc:
                raise ConnectionError(
                    f"Failed to fetch CBE financial data for {normalized}"
                ) from exc

        # Compile all available data
        financials = {
            "kbo_number": normalized,
            "kbo_formatted": self._format_kbo_for_lookup(kbo_number),
            "revenue": self.get_revenue(kbo_number),
            "employees": self.get_employee_count(kbo_number),
            "founding": self.get_founding_date(kbo_number),
            "company_size": None,
        }

        # Determine overall company size category
        if financials["employees"] and isinstance(financials["employees"], dict):
            financials["company_size"] = financials["employees"].get("employee_range")
        elif financials["revenue"] and isinstance(financials["revenue"], dict):
            # Estimate from revenue
            revenue = financials["revenue"].get("revenue_eur", 0)
            if revenue < 1_000_000:
                financials["company_size"] = "micro"
            elif revenue < 10_000_000:
                financials["company_size"] = "small"
            elif revenue < 50_000_000:
                financials["company_size"] = "medium"
            else:
                financials["company_size"] = "large"

        return financials

    async def enrich_profile_with_financials(self, profile: dict) -> dict:
        """
        Enrich a profile dict with CBE financial data.

        Args:
            profile: Tracardi profile dict

        Returns:
            Enriched profile
        """
        kbo = self._extract_kbo_from_profile(profile)
        if not kbo:
            return profile

        financials = await self.get_company_financials(kbo)

        if "traits" not in profile:
            profile["traits"] = {}

        # Add financial data to traits
        if financials["revenue"]:
            profile["traits"]["revenue_eur"] = financials["revenue"].get("revenue_eur")
            profile["traits"]["revenue_year"] = financials["revenue"].get("revenue_year")

        if financials["employees"]:
            profile["traits"]["employees"] = financials["employees"].get("employees")
            profile["traits"]["employee_range"] = financials["employees"].get("employee_range")
            profile["traits"]["company_size"] = financials["employees"].get("employee_range")

        if financials["founding"]:
            profile["traits"]["founding_date"] = financials["founding"].get("founding_date")
            profile["traits"]["founding_year"] = financials["founding"].get("founding_year")
            profile["traits"]["company_age"] = financials["founding"].get("company_age")

        # Add enrichment metadata
        profile["traits"]["cbe_financial_enrichment"] = {
            "enriched_at": datetime.now(UTC).isoformat(),
            "kbo_number": kbo,
            "has_revenue": financials["revenue"] is not None,
            "has_employees": financials["employees"] is not None,
            "has_founding": financials["founding"] is not None,
        }

        return profile

    def _extract_kbo_from_profile(self, profile: dict) -> str | None:
        """Extract KBO number from profile."""
        traits = profile.get("traits", {})

        # Direct KBO number
        kbo = traits.get("enterprise_number") or traits.get("kbo_number")
        if kbo:
            return self._normalize_kbo(kbo)

        # From kbo structure
        kbo_data = traits.get("kbo", {})
        if kbo_data:
            kbo = kbo_data.get("enterprise_number") or kbo_data.get("entity_number")
            if kbo:
                return self._normalize_kbo(kbo)

        return None


# Helper function for categorization
def categorize_size(employees: int) -> str:
    """
    Categorize company size based on employee count.

    EU definitions:
    - micro: < 10 employees
    - small: 10-49 employees
    - medium: 50-249 employees
    - large: 250+ employees
    """
    if employees < 10:
        return "micro"
    elif employees < 50:
        return "small"
    elif employees < 250:
        return "medium"
    else:
        return "large"
