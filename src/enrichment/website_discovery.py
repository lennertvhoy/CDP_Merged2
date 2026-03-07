"""
Website discovery via pattern matching and validation.

Tries common URL patterns and validates with HTTP requests.
Cost: €0 (no paid APIs)
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.config import settings
from src.core.cache import AsyncCache, MultiTierCache, RedisCache, SQLiteCache
from src.core.logger import get_logger
from src.core.rate_limit import AsyncRateLimiter
from src.enrichment.base import BaseEnricher
from src.enrichment.phone_discovery import PhoneDiscovery

logger = get_logger(__name__)


class WebsiteDiscoveryEnricher(BaseEnricher):
    """
    Discover company websites via pattern matching and validation.

    Strategy:
    1. Extract domain from email address
    2. Generate URL patterns from company name
    3. Validate with HTTP HEAD requests
    """

    # Generic email domains that aren't company websites
    GENERIC_DOMAINS = {
        "gmail.com",
        "hotmail.com",
        "outlook.com",
        "yahoo.com",
        "live.com",
        "icloud.com",
        "protonmail.com",
        "aol.com",
        "msn.com",
        "qq.com",
        # Belgian ISPs
        "skynet.be",
        "telenet.be",
        "proximus.be",
        "scarlet.be",
        "belgacom.be",
        "pandora.be",
        "fulladsl.be",
        "destiny.be",
        "edpnet.be",
    }

    # TLDs to try, in order of preference
    TLDS = [".be", ".com", ".eu", ".net", ".org", ".info"]
    MAX_DOMAIN_LABEL_LENGTH = 63

    # Legal forms to remove from company names
    LEGAL_FORMS = [
        "bvba",
        "nv",
        "sa",
        "sprl",
        "scrl",
        "scs",
        "sca",
        "comm.v",
        "commva",
        "vof",
        "vzw",
        "asbl",
        "ebvba",
        "bv",
        "cv",
        "cvba",
        "gcv",
        "geie",
        "se",
        "sicav",
        "sicaf",
        "fi",
        "bevek",
        "instelling",
        "stichting",
    ]

    def __init__(
        self,
        cache_dir: str | None = "./data/cache",
        cache_file: str = "website_cache.json",
        timeout: float = 10.0,
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
                l1 = SQLiteCache(db_path=db_path, table_name="websitediscoveryenricher")
                l2 = RedisCache(url=redis_url, prefix="cdp:website:", ttl=86400 * 7)  # 7-day TTL
                cache = MultiTierCache(l1=l1, l2=l2)
                logger.info("WebsiteDiscoveryEnricher: using MultiTierCache (SQLite + Redis)")
            else:
                logger.debug("WebsiteDiscoveryEnricher: REDIS_URL not set, using SQLiteCache only")

        # Wire the rate limiter (20 req/s matches the semaphore concurrency)
        rate_limiter = AsyncRateLimiter(calls=20, period=1.0)

        super().__init__(
            cache_dir=cache_dir,
            cache_file=cache_file,
            cache=cache,
            rate_limiter=rate_limiter,
        )
        self.timeout = timeout
        self._semaphore = asyncio.Semaphore(20)  # Limit concurrent HTTP requests
        self.phone_discovery = PhoneDiscovery(timeout=timeout)

    def _get_company_name(self, profile: dict) -> str | None:
        """Extract company name from profile."""
        traits = profile.get("traits", {})

        name = (traits.get("name") or "").strip()
        if name:
            return name

        # Try kbo structure
        kbo = traits.get("kbo", {})
        if kbo:
            denominations = kbo.get("denominations", [])
            if denominations and isinstance(denominations, list):
                for denom in denominations:
                    if isinstance(denom, dict):
                        name = (denom.get("name") or "").strip()
                        if name:
                            return name

        return None

    def _get_email(self, profile: dict) -> str | None:
        """Extract email from profile."""
        traits = profile.get("traits", {})

        email = (traits.get("email") or "").strip()
        if email and "@" in email:
            return email

        emails = traits.get("emails", [])
        if emails and isinstance(emails, list):
            for e in emails:
                if isinstance(e, str) and "@" in e:
                    return e.strip()

        # Try kbo contacts
        kbo = traits.get("kbo", {})
        if kbo:
            contacts = kbo.get("contacts", [])
            if contacts and isinstance(contacts, list):
                for contact in contacts:
                    if isinstance(contact, dict):
                        if contact.get("type") == "EMAIL" or contact.get("contactType") == "EMAIL":
                            value = contact.get("value") or contact.get("Value")
                            if value and "@" in value:
                                return value.strip()

        return None

    def _extract_domain_from_email(self, email: str) -> str | None:
        """Extract domain from email address."""
        if not email or "@" not in email:
            return None

        domain = email.split("@")[1].lower().strip()

        # Skip generic domains
        if domain in self.GENERIC_DOMAINS:
            return None

        return domain

    def _clean_company_name(self, name: str) -> str:
        """Clean company name for compact URL generation."""
        return "".join(self._tokenize_company_name(name))

    def _tokenize_company_name(self, name: str) -> list[str]:
        """Normalize a company name into domain-safe tokens."""
        clean = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
        clean = clean.lower()

        # Remove legal forms
        for form in self.LEGAL_FORMS:
            # Match as whole word
            clean = re.sub(rf"\b{re.escape(form)}\b", " ", clean)

        # Keep only domain-safe characters and normalize separators to spaces
        clean = re.sub(r"[^a-z0-9\s_-]", " ", clean)
        clean = re.sub(r"[_-]+", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()

        return [token for token in clean.split(" ") if token]

    def _generate_url_candidates(self, company_name: str) -> list[str]:
        """Generate URL candidates from company name."""
        tokens = self._tokenize_company_name(company_name)
        if not tokens:
            return []

        variants = ["".join(tokens)]
        if len(tokens) > 1:
            hyphenated_name = "-".join(tokens)
            if hyphenated_name not in variants:
                variants.append(hyphenated_name)

        valid_variants = [
            variant for variant in variants if 0 < len(variant) <= self.MAX_DOMAIN_LABEL_LENGTH
        ]
        if not valid_variants:
            return []

        candidates = []
        seen: set[str] = set()
        for tld in self.TLDS:
            for variant in valid_variants:
                for prefix in ("https://www.", "https://"):
                    candidate = f"{prefix}{variant}{tld}"
                    if candidate not in seen:
                        candidates.append(candidate)
                        seen.add(candidate)

        return candidates

    async def _check_website(self, url: str) -> dict | None:
        """
        Check if website is valid via HTTP request.

        Args:
            url: URL to check

        Returns:
            Dict with url info if valid, None otherwise
        """
        async with self._semaphore:
            try:
                async with httpx.AsyncClient() as client:
                    # Try HEAD first (faster)
                    try:
                        response = await client.head(
                            url,
                            timeout=self.timeout,
                            follow_redirects=True,
                            headers={"User-Agent": "CDP_Merged_Bot/1.0"},
                        )
                        if response.status_code < 400:
                            return {
                                "url": str(response.url),
                                "status_code": response.status_code,
                                "method": "HEAD",
                            }
                    except Exception as e:
                        logger.debug(
                            f"HEAD request failed for {url}", extra={"url": url, "error": str(e)}
                        )
                        # Still continue silently, but now we can debug

                    # Fallback to GET
                    response = await client.get(
                        url,
                        timeout=self.timeout,
                        follow_redirects=True,
                        headers={"User-Agent": "CDP_Merged_Bot/1.0"},
                    )
                    if response.status_code < 400:
                        return {
                            "url": str(response.url),
                            "status_code": response.status_code,
                            "method": "GET",
                        }

            except Exception as e:
                logger.debug(f"Website check failed for {url}: {e}")

        return None

    async def _scrape_website(self, url: str) -> dict:
        """Deep crawl website to extract emails, phones, and socials."""
        results: dict[str, list[str]] = {"emails": [], "phones": [], "socials": []}

        # Email Regex
        email_regex = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
        valid_prefixes = {"info", "contact", "sales", "support", "hello", "admin", "marketing"}

        async with self._semaphore:
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, follow_redirects=True
                ) as client:
                    # 1. Fetch Homepage
                    response = await client.get(url, headers={"User-Agent": "CDP_Merged_Bot/1.0"})
                    if response.status_code != 200:
                        return results

                    html = response.text
                    soup = BeautifulSoup(html, "html.parser")

                    pages_to_check = [(url, html, soup)]

                    # 2. Find Contact Pages
                    contact_keywords = [
                        "contact",
                        "about",
                        "about-us",
                        "contact-us",
                        "reach-us",
                        "get-in-touch",
                    ]
                    contact_urls = []
                    for link in soup.find_all("a", href=True):
                        href_attr = link.get("href")
                        href_str = (
                            href_attr[0]
                            if isinstance(href_attr, list) and href_attr
                            else str(href_attr or "")
                        )
                        href_lower = href_str.lower()
                        text = link.get_text(strip=True).lower()
                        if any(kw in href_lower for kw in contact_keywords) or any(
                            kw in text for kw in contact_keywords
                        ):
                            full_url = urljoin(url, href_str)
                            if full_url not in contact_urls and full_url.startswith(
                                ("http://", "https://")
                            ):
                                contact_urls.append(full_url)

                    # Fetch up to 2 contact pages
                    for contact_url in set(contact_urls[:2]):
                        try:
                            c_resp = await client.get(
                                contact_url, headers={"User-Agent": "CDP_Merged_Bot/1.0"}
                            )
                            if c_resp.status_code == 200:
                                c_soup = BeautifulSoup(c_resp.text, "html.parser")
                                pages_to_check.append((contact_url, c_resp.text, c_soup))
                        except Exception as e:
                            logger.debug(f"Contact page fetch failed {contact_url}: {e}")

                    # 3. Extract Data
                    extracted_emails = set()
                    extracted_phones = set()
                    extracted_socials = set()

                    for _page_url, page_html, page_soup in pages_to_check:
                        # Emails
                        for email_match in email_regex.findall(page_html):
                            email_match = email_match.lower()
                            prefix = email_match.split("@")[0]
                            if prefix in valid_prefixes:
                                extracted_emails.add(email_match)

                        # Phones
                        phones = self.phone_discovery._extract_phones_from_text(page_html)
                        for p in phones:
                            extracted_phones.add(p)

                        # Socials
                        for link in page_soup.find_all("a", href=True):
                            href_attr = link.get("href")
                            href_str = (
                                href_attr[0]
                                if isinstance(href_attr, list) and href_attr
                                else str(href_attr or "")
                            )
                            href_lower = href_str.lower()
                            if (
                                "linkedin.com/company/" in href_lower
                                or "facebook.com/" in href_lower
                            ):
                                extracted_socials.add(href_str)

                    results["emails"] = list(extracted_emails)
                    results["phones"] = list(extracted_phones)
                    results["socials"] = list(extracted_socials)

            except Exception as e:
                logger.debug(f"Scraping failed for {url}: {e}")

        return results

    async def discover_website(
        self,
        company_name: str,
        email: str | None = None,
    ) -> dict | None:
        """
        Discover website for a company.

        Args:
            company_name: Company name
            email: Optional email address

        Returns:
            Website info dict or None
        """
        cache_key = f"{company_name}_{email}"

        # Check cache
        cached = await self.cache.get(cache_key, default="MISS")
        if cached != "MISS":
            return cached

        # Strategy 1: Try email domain first
        if email:
            domain = self._extract_domain_from_email(email)
            if domain:
                for protocol in ["https://", "http://"]:
                    for prefix in ["www.", ""]:
                        url = f"{protocol}{prefix}{domain}"
                        result = await self._check_website(url)
                        if result:
                            await self.cache.set(cache_key, result)
                            return result

        # Strategy 2: Generate candidates from company name
        candidates = self._generate_url_candidates(company_name)

        # Check all candidates concurrently
        tasks = [self._check_website(url) for url in candidates]
        gather_results = await asyncio.gather(*tasks, return_exceptions=True)

        for gather_res in gather_results:
            if isinstance(gather_res, dict) and gather_res:
                await self.cache.set(cache_key, gather_res)
                return gather_res

        await self.cache.set(cache_key, None)
        return None

    def can_enrich(self, profile: dict) -> bool:
        """Check if profile has company name."""
        return bool(self._get_company_name(profile))

    async def enrich_profile(self, profile: dict) -> dict:
        """
        Enrich profile with discovered website.

        Args:
            profile: Tracardi profile dict

        Returns:
            Enriched profile
        """
        self.stats.total += 1

        company_name = self._get_company_name(profile)
        if not company_name:
            self.stats.skipped += 1
            return profile

        email = self._get_email(profile)

        try:
            website = await self.discover_website(company_name, email)

            if website:
                if "traits" not in profile:
                    profile["traits"] = {}

                profile["traits"]["website_url"] = website["url"]
                profile["traits"]["website_verified"] = True
                profile["traits"]["website_discovered_at"] = datetime.now(UTC).isoformat()
                profile["traits"]["website_discovery_method"] = "pattern_matching"

                # Extract domain for easy filtering
                parsed = urlparse(website["url"])
                profile["traits"]["website_domain"] = parsed.netloc

                # Deep crawl for contact data
                scraped_data = await self._scrape_website(website["url"])

                # Update emails
                if scraped_data["emails"]:
                    existing_emails = set(
                        profile["traits"].get("emails", [])
                        if isinstance(profile["traits"].get("emails"), list)
                        else []
                    )
                    existing_email = profile["traits"].get("email")
                    if existing_email:
                        existing_emails.add(existing_email)

                    new_emails = [e for e in scraped_data["emails"] if e not in existing_emails]
                    if new_emails:
                        if "emails" not in profile["traits"]:
                            profile["traits"]["emails"] = []
                        if isinstance(profile["traits"]["emails"], list):
                            profile["traits"]["emails"].extend(new_emails)
                        else:
                            profile["traits"]["emails"] = new_emails

                        # Set primary email if none
                        if not profile["traits"].get("email"):
                            profile["traits"]["email"] = new_emails[0]

                # Update phones
                if scraped_data["phones"]:
                    if not (
                        profile["traits"].get("phone")
                        or profile["traits"].get("contact_phone")
                        or profile["traits"].get("telephone")
                    ):
                        profile["traits"]["phone"] = scraped_data["phones"][0]
                        profile["traits"]["phone_source"] = "website_scraping"
                        profile["traits"]["phone_discovered"] = True

                # Update socials
                if scraped_data["socials"]:
                    existing_socials = set(
                        profile["traits"].get("social_links", [])
                        if isinstance(profile["traits"].get("social_links"), list)
                        else []
                    )
                    new_socials = [s for s in scraped_data["socials"] if s not in existing_socials]
                    if new_socials:
                        if "social_links" not in profile["traits"]:
                            profile["traits"]["social_links"] = []
                        if isinstance(profile["traits"]["social_links"], list):
                            profile["traits"]["social_links"].extend(new_socials)
                        else:
                            profile["traits"]["social_links"] = new_socials

                self.stats.success += 1
                logger.debug(f"Found website for {company_name[:30]}...: {website['url']}")
            else:
                if "traits" not in profile:
                    profile["traits"] = {}
                profile["traits"]["website_verified"] = False
                self.stats.failed += 1

        except Exception as e:
            logger.error(f"Website discovery error: {e}")
            self.stats.failed += 1

        return profile
