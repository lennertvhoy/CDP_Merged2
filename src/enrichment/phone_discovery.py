"""
Phone Number Discovery enrichment.

Expands phone number coverage by discovering from:
- Company websites (contact pages)
- CBE extended data
- Social profiles
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from src.core.logger import get_logger
from src.enrichment.base import BaseEnricher

logger = get_logger(__name__)


class PhoneDiscovery:
    """
    Discovers phone numbers from various sources.
    """

    # Belgian phone number patterns
    PHONE_PATTERNS = [
        # International format: +32 XXX XX XX XX
        r"\+32\s*\d{1,2}\s*\d{2,3}\s*\d{2}\s*\d{2}",
        # Local format: 0X XXX XX XX
        r"0\d{1,2}\s*\d{2,3}\s*\d{2}\s*\d{2}",
        # Local format without spaces: 0XXXXXXXXX
        r"0\d{8,9}",
        # International without spaces: +32XXXXXXXXX
        r"\+32\d{8,9}",
    ]

    # Compiled regex
    PHONE_REGEX = re.compile("|".join(f"({p})" for p in PHONE_PATTERNS), re.IGNORECASE)

    def __init__(self, timeout: float = 10.0, max_concurrent: int = 10):
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def _normalize_phone(self, phone: str) -> str | None:
        """Normalize phone number to standard format."""
        if not phone:
            return None

        # Remove all non-digit characters except +
        digits = "".join(c for c in phone if c.isdigit() or c == "+")

        # Must have at least 9 digits
        digit_count = len([c for c in digits if c.isdigit()])
        if digit_count < 9:
            return None

        # Convert to international format if starting with 0
        if digits.startswith("0") and not digits.startswith("00"):
            digits = "+32" + digits[1:]
        elif digits.startswith("00"):
            digits = "+" + digits[2:]
        elif not digits.startswith("+"):
            # Assume Belgian number
            digits = "+32" + digits

        # Validate Belgian number format
        if not digits.startswith("+32"):
            return None

        # Remove non-digits for final format check
        clean = digits.replace("+", "").replace(" ", "")
        if len(clean) not in (10, 11) or not clean.startswith("32"):
            return None

        return digits

    def _extract_phones_from_text(self, text: str) -> list[str]:
        """Extract phone numbers from text."""
        phones = []
        matches = self.PHONE_REGEX.findall(text)

        for match_group in matches:
            # match_group is a tuple of all groups, find non-empty
            for match in match_group:
                if match:
                    normalized = self._normalize_phone(match)
                    if normalized and normalized not in phones:
                        phones.append(normalized)

        return phones

    async def discover_from_website(self, website: str) -> str | None:
        """
        Scrape website for phone numbers.

        Args:
            website: Website URL

        Returns:
            Primary phone number or None
        """
        if not website:
            return None

        # Ensure URL has scheme
        if not website.startswith(("http://", "https://")):
            website = "https://" + website

        async with self._semaphore:
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, follow_redirects=True
                ) as client:
                    # Try main page first
                    response = await client.get(website)
                    if response.status_code != 200:
                        return None

                    html = response.text
                    soup = BeautifulSoup(html, "html.parser")

                    # Extract from entire page first
                    phones = self._extract_phones_from_text(html)

                    # Look for contact link
                    contact_urls = self._find_contact_links(soup, website)

                    # Try contact pages
                    for contact_url in contact_urls[:2]:  # Limit to 2 contact pages
                        try:
                            contact_response = await client.get(contact_url)
                            if contact_response.status_code == 200:
                                contact_phones = self._extract_phones_from_text(
                                    contact_response.text
                                )
                                phones.extend(contact_phones)
                        except httpx.RequestError as e:
                            logger.debug(
                                "contact_page_fetch_failed", url=contact_url, error=str(e)
                            )

                    # Return most common phone
                    if phones:
                        from collections import Counter

                        most_common = Counter(phones).most_common(1)[0][0]
                        return most_common

            except httpx.RequestError as e:
                logger.debug("website_phone_discovery_failed", url=website, error=str(e))

        return None

    def _find_contact_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """Find contact page URLs from website."""
        contact_urls = []

        # Keywords indicating contact pages
        contact_keywords = [
            "contact",
            "about",
            "about-us",
            "contact-us",
            "reach-us",
            "get-in-touch",
        ]

        for link in soup.find_all("a", href=True):
            href_attr = link.get("href")
            href_str = (
                href_attr[0] if isinstance(href_attr, list) and href_attr else str(href_attr or "")
            )
            href_lower = href_str.lower()
            text = link.get_text(strip=True).lower()

            # Check if href or text contains contact keywords
            is_contact = any(kw in href_lower for kw in contact_keywords) or any(
                kw in text for kw in contact_keywords
            )

            if is_contact:
                full_url = urljoin(base_url, href_str)
                contact_urls.append(full_url)

        return contact_urls

    async def discover_from_cbe(self, kbo_number: str, cbe_data: dict | None = None) -> str | None:
        """
        Extract phone from CBE data.

        Args:
            kbo_number: KBO number
            cbe_data: Pre-fetched CBE data (optional)

        Returns:
            Phone number or None
        """
        # If CBE data provided, extract from it
        if cbe_data:
            phones = self._extract_phones_from_cbe_data(cbe_data)
            if phones:
                return phones[0]

        # Otherwise, try to fetch via CBE extended client
        try:
            from src.services.cbe_extended import CBEExtendedClient

            client = CBEExtendedClient(use_api=True)

            # Fetch enterprise details
            enterprise = await client.fetch_enterprise_details(kbo_number)
            if enterprise:
                phones = self._extract_phones_from_cbe_data(enterprise)
                if phones:
                    return phones[0]
        except httpx.RequestError as e:
            logger.debug("cbe_phone_discovery_failed", kbo=kbo_number, error=str(e))

        return None

    def _extract_phones_from_cbe_data(self, cbe_data: dict) -> list[str]:
        """Extract phone numbers from CBE enterprise data."""
        phones = []

        try:
            # Try various fields where phone might be stored
            phone_fields = [
                "phone",
                "telephone",
                "tel",
                "contactPhone",
                "businessPhone",
                "phoneNumber",
            ]

            for field in phone_fields:
                value = cbe_data.get(field)
                if value:
                    normalized = self._normalize_phone(str(value))
                    if normalized:
                        phones.append(normalized)

            # Try contact points
            contacts = cbe_data.get("contactPoints", [])
            if isinstance(contacts, list):
                for contact in contacts:
                    if isinstance(contact, dict):
                        phone = contact.get("phone") or contact.get("telephone")
                        if phone:
                            normalized = self._normalize_phone(str(phone))
                            if normalized:
                                phones.append(normalized)

            # Try establishments
            establishments = cbe_data.get("establishments", [])
            if isinstance(establishments, list):
                for est in establishments:
                    if isinstance(est, dict):
                        phone = est.get("phone") or est.get("telephone")
                        if phone:
                            normalized = self._normalize_phone(str(phone))
                            if normalized:
                                phones.append(normalized)

            # Try address
            address = cbe_data.get("address", {})
            if isinstance(address, dict):
                phone = address.get("phone") or address.get("telephone")
                if phone:
                    normalized = self._normalize_phone(str(phone))
                    if normalized:
                        phones.append(normalized)

        except Exception as e:
            logger.debug("phone_extraction_from_cbe_failed", error=str(e))

        return phones

    async def discover_for_profile(self, profile: dict) -> str | None:
        """
        Discover phone number for a profile using all available methods.

        Args:
            profile: Tracardi profile dict

        Returns:
            Best phone number or None
        """
        traits = profile.get("traits", {})

        # Check if phone already exists
        existing = traits.get("phone") or traits.get("contact_phone") or traits.get("telephone")
        if existing:
            return self._normalize_phone(existing)

        # Try website discovery
        website = traits.get("website") or traits.get("url")
        if website:
            phone = await self.discover_from_website(website)
            if phone:
                return phone

        # Try CBE discovery
        kbo = traits.get("enterprise_number") or traits.get("kbo_number")
        if not kbo:
            kbo_data = traits.get("kbo")
            if isinstance(kbo_data, str):
                kbo = kbo_data
            elif isinstance(kbo_data, dict):
                kbo = kbo_data.get("enterprise_number") or kbo_data.get("entity_number")

        if kbo:
            phone = await self.discover_from_cbe(kbo)
            if phone:
                return phone

        return None


class PhoneDiscoveryEnricher(BaseEnricher):
    """
    Enricher that discovers missing phone numbers.
    """

    def __init__(
        self,
        cache_dir: str | None = "./data/cache",
        cache_file: str = "phone_discovery_cache.json",
        timeout: float = 10.0,
        cache=None,
    ):
        super().__init__(cache_dir=cache_dir, cache_file=cache_file, cache=cache)
        self.discovery = PhoneDiscovery(timeout=timeout)

    def can_enrich(self, profile: dict) -> bool:
        """Check if profile can be enriched (missing phone but has website or KBO)."""
        traits = profile.get("traits", {})

        # Already has phone
        if traits.get("phone") or traits.get("contact_phone") or traits.get("telephone"):
            return False

        # Has website or KBO for discovery
        has_website = bool(traits.get("website") or traits.get("url"))
        has_kbo = bool(
            traits.get("enterprise_number")
            or traits.get("kbo_number")
            or traits.get("kbo", {}).get("enterprise_number")
        )

        return has_website or has_kbo

    async def enrich_profile(self, profile: dict) -> dict:
        """Enrich profile with discovered phone number."""
        self.stats.total += 1

        phone = await self.discovery.discover_for_profile(profile)

        if phone:
            if "traits" not in profile:
                profile["traits"] = {}

            profile["traits"]["phone"] = phone
            profile["traits"]["phone_discovered"] = True
            profile["traits"]["phone_source"] = "discovery"

            self.stats.success += 1
            logger.info("phone_discovered", kbo=profile.get("traits", {}).get("kbo_number"))
        else:
            self.stats.skipped += 1

        return profile
