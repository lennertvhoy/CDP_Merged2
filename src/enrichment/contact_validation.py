"""
Contact validation (email/phone format validation).

Validates and normalizes contact information.
Cost: €0 (regex operations)
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime

import aiohttp

from src.core.logger import get_logger
from src.enrichment.base import BaseEnricher

logger = get_logger(__name__)


class ContactValidationEnricher(BaseEnricher):
    """
    Validate and normalize email/phone contact information.

    Provides:
    - Email format validation
    - Belgian phone normalization
    - Contact quality scoring
    """

    # Email validation regex (simplified but effective)
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    # Disposable email domains
    DISPOSABLE_DOMAINS = {
        "tempmail.com",
        "throwaway.com",
        "mailinator.com",
        "guerrillamail.com",
        "10minutemail.com",
        "yopmail.com",
        "fakeinbox.com",
        "tempinbox.com",
    }

    def __init__(
        self,
        cache_dir: str | None = "./data/cache",
        cache_file: str = "contact_validation_cache.json",
    ):
        super().__init__(cache_dir=cache_dir, cache_file=cache_file)
        self.zerobounce_api_key = os.getenv("ZEROBOUNCE_API_KEY")

    def _get_emails(self, profile: dict) -> list[str]:
        """Extract all emails from profile."""
        traits = profile.get("traits", {})
        emails = []

        # Primary email
        email = (traits.get("email") or "").strip()
        if email:
            emails.append(email)

        # Email list
        email_list = traits.get("emails", [])
        if isinstance(email_list, list):
            for e in email_list:
                if isinstance(e, str):
                    emails.append(e.strip())

        # KBO contacts
        kbo = traits.get("kbo", {})
        if kbo:
            contacts = kbo.get("contacts", [])
            if isinstance(contacts, list):
                for contact in contacts:
                    if isinstance(contact, dict):
                        if contact.get("type") == "EMAIL" or contact.get("contactType") == "EMAIL":
                            value = contact.get("value") or contact.get("Value")
                            if value and isinstance(value, str):
                                emails.append(value.strip())

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for e in emails:
            e_lower = e.lower()
            if e_lower not in seen:
                seen.add(e_lower)
                unique.append(e)

        return unique

    def _get_phones(self, profile: dict) -> list[str]:
        """Extract all phone numbers from profile."""
        traits = profile.get("traits", {})
        phones = []

        # Primary phone
        phone = (traits.get("phone") or "").strip()
        if phone:
            phones.append(phone)

        # Phone list
        phone_list = traits.get("phones", [])
        if isinstance(phone_list, list):
            for p in phone_list:
                if isinstance(p, str):
                    phones.append(p.strip())

        # KBO contacts
        kbo = traits.get("kbo", {})
        if kbo:
            contacts = kbo.get("contacts", [])
            if isinstance(contacts, list):
                for contact in contacts:
                    if isinstance(contact, dict):
                        if contact.get("type") == "TEL" or contact.get("contactType") == "TEL":
                            value = contact.get("value") or contact.get("Value")
                            if value and isinstance(value, str):
                                phones.append(value.strip())

        # Remove duplicates
        seen = set()
        unique = []
        for p in phones:
            p_clean = re.sub(r"\D", "", p)
            if p_clean not in seen:
                seen.add(p_clean)
                unique.append(p)

        return unique

    async def validate_email(
        self, email: str, session: aiohttp.ClientSession | None = None
    ) -> dict:
        """
        Validate email format and verify via ZeroBounce if API key is present.

        Args:
            email: Email address to validate
            session: Optional aiohttp ClientSession

        Returns:
            Validation result dict
        """
        if not email:
            return {
                "email": email,
                "valid": False,
                "reason": "empty",
                "is_disposable": False,
            }

        # Basic format check
        if not self.EMAIL_PATTERN.match(email):
            return {
                "email": email,
                "valid": False,
                "reason": "invalid_format",
                "is_disposable": False,
            }

        domain = email.split("@")[1].lower()

        # Check disposable domain
        is_disposable = domain in self.DISPOSABLE_DOMAINS

        # If no ZeroBounce key, return basic validation result
        if not self.zerobounce_api_key:
            return {
                "email": email,
                "valid": True,
                "reason": None,
                "is_disposable": is_disposable,
                "domain": domain,
            }

        # Call ZeroBounce
        url = f"https://api.zerobounce.net/v2/validate?api_key={self.zerobounce_api_key}&email={email}"
        timeout = aiohttp.ClientTimeout(total=5)
        try:
            if session:
                async with session.get(url, timeout=timeout) as response:
                    data = await response.json()
            else:
                async with aiohttp.ClientSession() as new_session:
                    async with new_session.get(url, timeout=timeout) as response:
                        data = await response.json()

            status = data.get("status")
            sub_status = data.get("sub_status")

            is_valid = status == "valid" or status == "catch-all"

            return {
                "email": email,
                "valid": is_valid,
                "reason": sub_status if not is_valid else None,
                "is_disposable": is_disposable
                or (status == "do_not_mail" and sub_status == "disposable"),
                "domain": domain,
                "status": status,
                "sub_status": sub_status,
            }
        except Exception as e:
            logger.error(f"ZeroBounce validation failed for {email}: {e}")
            # Fallback to regex validation on API failure
            return {
                "email": email,
                "valid": True,
                "reason": "zerobounce_api_error",
                "is_disposable": is_disposable,
                "domain": domain,
            }

    def normalize_belgian_phone(self, phone: str) -> str | None:
        """
        Normalize Belgian phone number to E.164 format.

        Args:
            phone: Phone number string

        Returns:
            Normalized phone number or None
        """
        if not phone:
            return None

        # Keep leading '+' if present
        has_plus = phone.strip().startswith("+")

        # Remove all non-digits
        digits = re.sub(r"\D", "", phone)

        if not digits:
            return None

        if has_plus:
            digits = "+" + digits

        if digits.startswith("00"):
            digits = "+" + digits[2:]

        # Belgian numbers typically:
        # - Landlines: 0x xxx xx xx (9 digits starting with 0)
        # - Mobile: 04xx xx xx xx (10 digits starting with 04)
        # - International: +32 x xx xx xx xx

        # If starts with 0, replace with +32
        if digits.startswith("0"):
            digits = "+32" + digits[1:]

        # If doesn't start with + and looks like a valid length, add +32
        elif not digits.startswith("+") and len(digits) >= 8:
            if digits.startswith("32"):
                digits = "+" + digits
            else:
                digits = "+32" + digits

        # Validate Belgian number format
        # Should be +32 followed by 8-9 digits
        if not re.match(r"^\+32\d{8,9}$", digits):
            # Maybe it's already valid international format
            if not re.match(r"^\+\d{10,15}$", digits):
                return None

        return digits

    def validate_phone(self, phone: str) -> dict:
        """
        Validate phone number.

        Args:
            phone: Phone number to validate

        Returns:
            Validation result dict
        """
        if not phone:
            return {
                "phone": phone,
                "valid": False,
                "normalized": None,
                "reason": "empty",
            }

        normalized = self.normalize_belgian_phone(phone)

        if not normalized:
            return {
                "phone": phone,
                "valid": False,
                "normalized": None,
                "reason": "invalid_format",
            }

        return {
            "phone": phone,
            "valid": True,
            "normalized": normalized,
            "reason": None,
        }

    def can_enrich(self, profile: dict) -> bool:
        """Check if profile has any contact info."""
        return bool(self._get_emails(profile) or self._get_phones(profile))

    async def enrich_profile(self, profile: dict) -> dict:
        """
        Enrich profile with validated contact information.

        Args:
            profile: Tracardi profile dict

        Returns:
            Enriched profile
        """
        self.stats.total += 1

        if not self.can_enrich(profile):
            self.stats.skipped += 1
            return profile

        if "traits" not in profile:
            profile["traits"] = {}

        # Validate emails
        emails = self._get_emails(profile)
        email_validation_results = []
        valid_emails = []

        if emails:
            async with aiohttp.ClientSession() as session:
                for email in emails:
                    result = await self.validate_email(email, session=session)
                    email_validation_results.append(result)
                    if result["valid"] and not result.get("is_disposable"):
                        valid_emails.append(result["email"])

        # Validate phones
        phones = self._get_phones(profile)
        phone_validation_results = []
        valid_phones = []

        for phone in phones:
            result = self.validate_phone(phone)
            phone_validation_results.append(result)
            if result["valid"]:
                valid_phones.append(result["normalized"])

        # Update profile
        profile["traits"]["email_validation"] = {
            "total": len(emails),
            "valid": len([e for e in email_validation_results if e["valid"]]),
            "invalid": len([e for e in email_validation_results if not e["valid"]]),
            "disposable": len([e for e in email_validation_results if e.get("is_disposable")]),
            "validated_at": datetime.now(UTC).isoformat(),
        }

        profile["traits"]["phone_validation"] = {
            "total": len(phones),
            "valid": len([p for p in phone_validation_results if p["valid"]]),
            "invalid": len([p for p in phone_validation_results if not p["valid"]]),
            "validated_at": datetime.now(UTC).isoformat(),
        }

        # Store normalized contacts
        if valid_emails:
            profile["traits"]["email_normalized"] = valid_emails[0]
            profile["traits"]["emails_normalized"] = valid_emails

        if valid_phones:
            profile["traits"]["phone_normalized"] = valid_phones[0]
            profile["traits"]["phones_normalized"] = valid_phones

        # Calculate contact quality score
        email_score = 1.0 if valid_emails else 0.0
        phone_score = 1.0 if valid_phones else 0.0

        profile["traits"]["contact_quality_score"] = (email_score + phone_score) / 2
        profile["traits"]["contact_validated_at"] = datetime.now(UTC).isoformat()

        self.stats.success += 1

        return profile
