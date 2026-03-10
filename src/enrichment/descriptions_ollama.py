"""
Company description enrichment via local Ollama LLM.

Generates business descriptions from NACE codes using local inference.
Cost: FREE (runs on local GPU/CPU)

Usage:
    # Use Ollama instead of Azure OpenAI
    export DESCRIPTION_ENRICHER=ollama
    export OLLAMA_MODEL=llama3.1:8b  # or llama3.2:3b, mistral, etc.

    # Then run enrichment as normal
    python scripts/enrich_companies_batch.py --enrichers description
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from src.core.cache import AsyncCache
from src.core.logger import get_logger
from src.enrichment.descriptions import _nace_label

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


class OllamaDescriptionEnricher:
    """
    Generate company descriptions using local Ollama LLM.

    Uses NACE codes to generate professional business descriptions.
    Implements caching by NACE code to minimize redundant inference.

    Much cheaper than Azure OpenAI (FREE vs ~€20-40 for 516K profiles)
    but may have slightly lower quality depending on the model used.
    """

    def __init__(
        self,
        cache_dir: str | None = "./data/cache",
        cache_file: str = "descriptions_cache_ollama.json",
        ollama_url: str | None = None,
        model: str | None = None,
        cache: AsyncCache | None = None,
    ):
        from pathlib import Path

        from src.config import settings
        from src.core.cache import MultiTierCache, RedisCache, SQLiteCache

        # Build multi-tier cache when Redis is configured and no explicit cache provided.
        if cache is None:
            redis_url = getattr(settings, "REDIS_URL", None)
            if redis_url:
                db_file = cache_file.replace(".json", ".db")
                db_path = Path(cache_dir or "./data/cache") / db_file
                db_path.parent.mkdir(parents=True, exist_ok=True)
                l1 = SQLiteCache(db_path=db_path, table_name="ollama_description_enricher")
                l2 = RedisCache(url=redis_url, prefix="cdp:desc:ollama:", ttl=86400 * 30)
                cache = MultiTierCache(l1=l1, l2=l2)
                logger.info("OllamaDescriptionEnricher: using MultiTierCache (SQLite + Redis)")
            else:
                logger.debug("OllamaDescriptionEnricher: REDIS_URL not set, using SQLiteCache only")

        # Initialize cache from parent pattern
        if cache is None:
            db_file = cache_file.replace(".json", ".db")
            db_path = Path(cache_dir or "./data/cache") / db_file
            db_path.parent.mkdir(parents=True, exist_ok=True)
            cache = SQLiteCache(db_path=db_path, table_name="ollama_description_enricher")

        self.cache = cache
        self.ollama_url = ollama_url or "http://localhost:11434"
        self.model = model or "llama3.1:8b"

        # Stats tracking
        self.tokens_used = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.inference_count = 0

        # Stats object for compatibility with DescriptionEnricher interface
        self.stats = type('Stats', (), {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
        })()

    def _get_nace_codes(self, profile: dict) -> list[str]:
        """Extract NACE codes from profile."""
        traits = profile.get("traits", {})

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
        """Build prompt for Ollama with human-readable NACE sector labels."""
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
        # Include model name in cache key for model-specific caching
        nace_part = ",".join(sorted(nace_codes)) if nace_codes else "unknown"
        return f"{self.model}:{nace_part}"

    @_retry
    async def generate_description(
        self,
        company_name: str,
        nace_codes: list[str],
    ) -> str | None:
        """
        Generate description for a company using local Ollama.

        Args:
            company_name: Company name
            nace_codes: List of NACE codes

        Returns:
            Generated description or None
        """
        cache_key = self._get_cache_key(nace_codes)

        # Check cache
        cached = await self.cache.get(cache_key, default="MISS")
        if cached != "MISS":
            logger.debug(f"Cache hit for NACE codes: {cache_key}")
            self.cache_hits += 1
            return cached

        self.cache_misses += 1
        prompt = self._build_prompt(company_name, nace_codes)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 150,
            },
        }

        url = f"{self.ollama_url}/api/generate"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=60.0)
                response.raise_for_status()

                data = response.json()
                description = data.get("response", "").strip()

                # Clean up common LLM artifacts
                description = self._clean_description(description)

                # Track stats
                self.inference_count += 1
                eval_count = data.get("eval_count", 0)
                self.tokens_used += eval_count

                # Cache result
                await self.cache.set(cache_key, description)

                logger.debug(f"Generated description for {company_name[:30]}... via Ollama")
                return description

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error {e.response.status_code}: {e.response.text[:200]}")
            raise
        except (httpx.RequestError, ValueError) as e:
            logger.error(f"Error generating description with Ollama: {e}")
            raise

    def _clean_description(self, description: str) -> str:
        """Clean up common LLM artifacts from the description."""
        # Remove common prefixes the model might add
        prefixes_to_remove = [
            "Here is a concise and professional 2-sentence business description for ",
            "Here is a professional business description for ",
            "Business description: ",
            "Description: ",
            "Here is the description:\n\n",
        ]

        for prefix in prefixes_to_remove:
            if description.lower().startswith(prefix.lower()):
                description = description[len(prefix):]

        # Remove leading/trailing whitespace and newlines
        description = description.strip()

        # If there are multiple paragraphs, take only the first one
        lines = description.split('\n')
        if len(lines) > 1:
            # Find the first non-empty line that looks like a description
            for line in lines:
                line = line.strip()
                if line and not line.startswith('Here') and not line.startswith('This'):
                    description = line
                    break

        return description.strip()

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

        company_name = self._get_company_name(profile)

        try:
            description = await self.generate_description(company_name, nace_codes)

            if description:
                if "traits" not in profile:
                    profile["traits"] = {}

                profile["traits"]["business_description"] = description
                profile["traits"]["business_description_source"] = f"ollama:{self.model}"
                profile["traits"]["business_description_nace_codes"] = nace_codes
                profile["traits"]["business_description_model"] = self.model
                profile["traits"]["business_description_enriched_at"] = datetime.now(
                    UTC
                ).isoformat()

                self.stats.success += 1
            else:
                self.stats.failed += 1

        except Exception as e:
            logger.error(f"Ollama description enrichment error: {e}")
            self.stats.failed += 1

        return profile

    def get_cost_estimate(self, profile_count: int, unique_nace_ratio: float = 0.1) -> dict:
        """
        Estimate "cost" for processing profiles (always $0 for Ollama).

        Args:
            profile_count: Number of profiles
            unique_nace_ratio: Ratio of unique NACE codes (default 10%)

        Returns:
            Cost estimate dict (all zeros since Ollama is free)
        """
        unique_count = int(profile_count * unique_nace_ratio)

        # Estimate tokens for tracking purposes (not cost)
        est_input_tokens = unique_count * 100
        est_output_tokens = unique_count * 50

        return {
            "profile_count": profile_count,
            "unique_nace_codes": unique_count,
            "estimated_input_tokens": est_input_tokens,
            "estimated_output_tokens": est_output_tokens,
            "estimated_compute_time_minutes": unique_count * 0.5,  # Approximate
            "estimated_total_cost_usd": 0.0,
            "estimated_total_cost_eur": 0.0,
            "note": "Ollama runs locally - no API costs, only compute/electricity",
        }

    def get_stats(self) -> dict[str, Any]:
        """Get enrichment statistics."""
        return {
            "total": self.stats.total,
            "success": self.stats.success,
            "failed": self.stats.failed,
            "skipped": self.stats.skipped,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "inference_count": self.inference_count,
            "tokens_used": self.tokens_used,
            "model": self.model,
        }
