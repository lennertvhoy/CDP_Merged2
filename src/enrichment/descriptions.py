"""
Company description enrichment via Azure OpenAI.

Generates business descriptions from NACE codes.
Costs ~€20-40 for 516K profiles (with caching/deduplication).
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.config import settings
from src.core.cache import AsyncCache, MultiTierCache, RedisCache, SQLiteCache
from src.core.logger import get_logger
from src.enrichment.base import BaseEnricher

logger = get_logger(__name__)

# Human-readable sector labels for common Belgian NACE code prefixes.
# Keeps GPT prompts meaningful without sending raw numeric codes alone.
NACE_SECTOR_MAP: dict[str, str] = {
    "01": "agriculture & crop farming",
    "10": "food manufacturing",
    "20": "chemical production",
    "25": "metal fabrication",
    "41": "construction & building",
    "45": "automotive trade & repair",
    "46": "wholesale trade",
    "47": "retail",
    "49": "land transport & logistics",
    "56": "food & beverage services",
    "62": "software & IT services",
    "63": "data & information services",
    "64": "financial services",
    "68": "real estate",
    "69": "legal services",
    "70": "management consulting",
    "71": "engineering & architecture",
    "73": "advertising & marketing",
    "74": "design & creative services",
    "77": "equipment rental",
    "81": "facility management & cleaning",
    "85": "education & training",
    "86": "healthcare & medical",
    "90": "arts & entertainment",
    "96": "personal care services",
}


def _nace_label(code: str) -> str:
    """Return human-readable sector label for a NACE code, or the raw code."""
    prefix = code[:2]
    label = NACE_SECTOR_MAP.get(prefix)
    return f"{code} ({label})" if label else code


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return False


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    reraise=True,
)


class DescriptionEnricher(BaseEnricher):
    """
    Generate company descriptions using Azure OpenAI.

    Uses NACE codes to generate professional business descriptions.
    Implements caching by NACE code to minimize API costs.
    """

    def __init__(
        self,
        cache_dir: str | None = "./data/cache",
        cache_file: str = "descriptions_cache.json",
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
        cache: AsyncCache | None = None,
    ):
        # Build multi-tier cache when Redis is configured and no explicit cache provided.
        if cache is None:
            redis_url = getattr(settings, "REDIS_URL", None)
            if redis_url:
                db_file = cache_file.replace(".json", ".db")
                from pathlib import Path

                db_path = Path(cache_dir or "./data/cache") / db_file
                db_path.parent.mkdir(parents=True, exist_ok=True)
                l1 = SQLiteCache(db_path=db_path, table_name="descriptionenricher")
                l2 = RedisCache(url=redis_url, prefix="cdp:desc:", ttl=86400 * 30)  # 30-day TTL
                cache = MultiTierCache(l1=l1, l2=l2)
                logger.info("DescriptionEnricher: using MultiTierCache (SQLite + Redis)")
            else:
                logger.debug("DescriptionEnricher: REDIS_URL not set, using SQLiteCache only")

        super().__init__(cache_dir=cache_dir, cache_file=cache_file, cache=cache, max_concurrent=2)

        self.endpoint = endpoint or settings.AZURE_OPENAI_ENDPOINT
        self.api_key = api_key or settings.AZURE_OPENAI_API_KEY
        self.deployment = deployment or settings.AZURE_OPENAI_DEPLOYMENT_NAME or "gpt-5"
        self.api_version = settings.AZURE_OPENAI_API_VERSION

        # Cost tracking (approximate)
        self.tokens_used = 0
        self.estimated_cost_usd = 0.0

        # GPT-4o-mini pricing (as of 2024)
        self.INPUT_PRICE_PER_1K = 0.00015  # $0.15 per 1M tokens = $0.00015 per 1K
        self.OUTPUT_PRICE_PER_1K = 0.0006  # $0.60 per 1M tokens = $0.0006 per 1K

    def _get_nace_codes(self, profile: dict) -> list[str]:
        """Extract NACE codes from profile."""
        traits = profile.get("traits", {})

        # Try different possible field names
        nace_codes = traits.get("nace_codes", [])
        if isinstance(nace_codes, str):
            nace_codes = [nace_codes]

        # Also check kbo sub-structure
        kbo = traits.get("kbo", {})
        if kbo and "activities" in kbo:
            activities = kbo["activities"]
            if isinstance(activities, list):
                for activity in activities:
                    if isinstance(activity, dict):
                        nace = activity.get("naceCode") or activity.get("nace_code")
                        if nace and nace not in nace_codes:
                            nace_codes.append(nace)

        return [n for n in nace_codes if n]

    def _get_company_name(self, profile: dict) -> str:
        """Extract company name from profile."""
        traits = profile.get("traits", {})

        name = traits.get("name", "")
        if name:
            return name

        # Try kbo structure
        kbo = traits.get("kbo", {})
        if kbo:
            denominations = kbo.get("denominations", [])
            if denominations and isinstance(denominations, list):
                return denominations[0].get("name", "Unknown")

        return "Unknown"

    def _build_prompt(self, company_name: str, nace_codes: list[str]) -> str:
        """Build prompt for Azure OpenAI with human-readable NACE sector labels."""
        if nace_codes:
            labelled = [_nace_label(c) for c in nace_codes]
            nace_str = ", ".join(labelled)
        else:
            nace_str = "various business activities"

        return f"""Generate a concise, professional 2-sentence business description for a Belgian B2B directory.

Company Name: {company_name}
NACE Activity Codes: {nace_str}

Requirements:
- Professional, informative tone suitable for business directory
- Mention main business activities based on NACE codes
- No marketing language or promotional content
- Plain text, no bullet points or markdown
- Focus on what the company does, not how great it is

Description:"""

    def _get_cache_key(self, nace_codes: list[str]) -> str:
        """Generate cache key from sorted NACE codes."""
        return ",".join(sorted(nace_codes)) if nace_codes else "unknown"

    @_retry
    async def generate_description(
        self,
        company_name: str,
        nace_codes: list[str],
    ) -> str | None:
        """
        Generate description for a company.

        Args:
            company_name: Company name
            nace_codes: List of NACE codes

        Returns:
            Generated description or None
        """
        if not self.endpoint or not self.api_key:
            logger.warning("Azure OpenAI not configured")
            return None

        cache_key = self._get_cache_key(nace_codes)

        # Check cache
        cached = await self.cache.get(cache_key, default="MISS")
        if cached != "MISS":
            logger.debug(f"Cache hit for NACE codes: {cache_key}")
            return cached

        prompt = self._build_prompt(company_name, nace_codes)

        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key,
        }

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates concise, professional company descriptions for B2B directories.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 150,
            "temperature": 0.3,
        }

        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=30.0)
                response.raise_for_status()

                data = response.json()
                # FIX: choices is a list; must index [0] before accessing "message"
                description = data["choices"][0]["message"]["content"].strip()

                # Track usage for cost estimation
                usage = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)

                self.tokens_used += prompt_tokens + completion_tokens
                self.estimated_cost_usd += (prompt_tokens / 1000 * self.INPUT_PRICE_PER_1K) + (
                    completion_tokens / 1000 * self.OUTPUT_PRICE_PER_1K
                )

                # Cache result
                await self.cache.set(cache_key, description)

                logger.debug(f"Generated description for {company_name[:30]}...")
                return description

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Azure OpenAI HTTP error {e.response.status_code}: {e.response.text[:200]}"
            )
            raise
        except (httpx.RequestError, ValueError) as e:
            logger.error(f"Error generating description: {e}")
            raise

    def can_enrich(self, profile: dict) -> bool:
        """Check if profile has NACE codes."""
        return bool(self._get_nace_codes(profile))

    async def enrich_profile(self, profile: dict) -> dict:
        """
        Enrich profile with AI-generated description.

        Args:
            profile: Tracardi profile dict

        Returns:
            Enriched profile
        """
        self.stats.total += 1

        nace_codes = self._get_nace_codes(profile)
        if not nace_codes:
            self.stats.skipped += 1
            return profile

        # generate_description() handles its own cache lookup internally.
        # We do NOT duplicate the cache.get() here to avoid two round-trips
        # per cache miss; the source tag tells us whether it was a cache hit.
        company_name = self._get_company_name(profile)

        try:
            description = await self.generate_description(company_name, nace_codes)

            if description:
                if "traits" not in profile:
                    profile["traits"] = {}

                profile["traits"]["business_description"] = description
                # generate_description() sets the cache; we can't distinguish
                # hit vs miss here, so use a neutral source tag.
                profile["traits"]["business_description_source"] = "azure_openai"
                profile["traits"]["business_description_nace_codes"] = nace_codes
                profile["traits"]["business_description_model"] = self.deployment
                profile["traits"]["business_description_enriched_at"] = datetime.now(
                    UTC
                ).isoformat()

                self.stats.success += 1
            else:
                self.stats.failed += 1

        except (KeyError, TypeError) as e:
            logger.error(f"Description enrichment error: {e}")
            self.stats.failed += 1

        return profile

    def get_cost_estimate(self, profile_count: int, unique_nace_ratio: float = 0.1) -> dict:
        """
        Estimate cost for processing profiles.

        Args:
            profile_count: Number of profiles
            unique_nace_ratio: Ratio of unique NACE codes (default 10%)

        Returns:
            Cost estimate dict
        """
        unique_count = int(profile_count * unique_nace_ratio)

        # Estimate tokens: ~100 input + ~50 output per unique NACE
        est_input_tokens = unique_count * 100
        est_output_tokens = unique_count * 50

        est_input_cost = est_input_tokens / 1000 * self.INPUT_PRICE_PER_1K
        est_output_cost = est_output_tokens / 1000 * self.OUTPUT_PRICE_PER_1K
        total_cost = est_input_cost + est_output_cost

        return {
            "profile_count": profile_count,
            "unique_nace_codes": unique_count,
            "estimated_input_tokens": est_input_tokens,
            "estimated_output_tokens": est_output_tokens,
            "estimated_input_cost_usd": round(est_input_cost, 2),
            "estimated_output_cost_usd": round(est_output_cost, 2),
            "estimated_total_cost_usd": round(total_cost, 2),
            "estimated_total_cost_eur": round(total_cost * 0.92, 2),  # Approx EUR
        }
