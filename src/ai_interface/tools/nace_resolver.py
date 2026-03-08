"""NACE Code Resolution Tools.

This module provides tools for resolving industry keywords to NACE activity codes
and juridical form codes.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

from langchain_core.tools import tool

from src.core.logger import get_logger

logger = get_logger(__name__)


def _load_json_data(filename: str) -> dict:
    """Load a JSON data file from src/data/, falling back to empty dict."""
    # Try pathlib relative to this file
    data_path = Path(__file__).parent.parent.parent / "data" / filename
    if data_path.exists():
        try:
            return json.loads(data_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("data_file_load_failed", filename=filename, error=str(exc))
    logger.warning("data_file_not_found", filename=filename, path=str(data_path))
    return {}


NACE_CODES: dict[str, str] = _load_json_data("nace_codes.json")
JURIDICAL_CODES: dict[str, str] = _load_json_data("juridical_codes.json")


def _normalize_text(value: str) -> str:
    """Lowercase and fold accents for resilient cross-language matching."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_folded = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    compact = re.sub(r"[^a-z0-9]+", " ", ascii_folded.lower()).strip()
    return re.sub(r"\s+", " ", compact)


def _load_kbo_nace_codes() -> dict[str, str]:
    """Load rich NACE descriptions from local KBO code data when available."""
    root = Path(__file__).resolve().parents[2]
    csv_path = root / "data" / "kbo" / "code.csv"
    if not csv_path.exists():
        return {}

    descriptions: dict[str, set[str]] = {}
    try:
        with csv_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                category = (row.get("Category") or "").strip()
                code = (row.get("Code") or "").strip()
                description = (row.get("Description") or "").strip()
                if category not in {"Nace2008", "Nace2025"}:
                    continue
                if not (code.isdigit() and len(code) == 5):
                    continue
                if not description:
                    continue
                descriptions.setdefault(code, set()).add(description)
    except (csv.Error, OSError) as exc:
        logger.warning("kbo_nace_load_failed", path=str(csv_path), error=str(exc))
        return {}

    return {code: " / ".join(sorted(values)) for code, values in descriptions.items()}


def _load_nace_catalog() -> dict[str, str]:
    """Compose static + KBO-sourced NACE descriptions into one searchable catalog."""
    catalog: dict[str, set[str]] = {}
    for code, description in NACE_CODES.items():
        catalog.setdefault(code, set()).add(description)

    for code, description in _load_kbo_nace_codes().items():
        catalog.setdefault(code, set()).add(description)

    merged: dict[str, str] = {}
    for code, descriptions in catalog.items():
        merged[code] = " / ".join(sorted(descriptions))
    return merged


NACE_CATALOG: dict[str, str] = _load_nace_catalog()


DOMAIN_SYNONYMS: dict[str, set[str]] = {
    "it": {"it", "ict", "information technology", "software", "computer", "tech", "technology"},
    "restaurant": {
        "restaurant",
        "restaurants",
        "horeca",
        "food service",
        "restauration",
        "restauratie",
        "dining",
        "eatery",
    },
    "pita": {
        "pita",
        "pitas",
        "pita shop",
        "pita winkel",
        "pitta",
        "pitterie",
        "pita restaurant",
        "snack",
        "snackbar",
        "snack bar",
        "fast food",
        "kebab",
        "doner",
        "shawarma",
        "falafel",
        "mediterranean food",
        "middle eastern food",
    },
    "barber": {
        "barber",
        "barbers",
        "barbershop",
        "barber shop",
        "hairdresser",
        "hairdressers",
        "hairstylist",
        "coiffure",
        "coiffeur",
        "coiffeuse",
        "kapper",
        "kappers",
        "kapsalon",
        "kapsalons",
        "haarverzorging",
    },
    "dentist": {
        "dentist",
        "dentists",
        "dental",
        "dentiste",
        "dentistes",
        "dentaire",
        "tandarts",
        "tandartsen",
        "tandartspraktijk",
    },
    "plumber": {
        "plumber",
        "plumbers",
        "plumbing",
        "plomberie",
        "loodgieter",
        "loodgieters",
        "loodgieterswerk",
    },
    "bakery": {
        "bakery",
        "bakeries",
        "baker",
        "bakers",
        "bread",
        "pastry",
        "patisserie",
        "boulangerie",
        "boulanger",
        "boulangeries",
        "bakker",
        "bakkers",
        "bakkerij",
        "bakkerijen",
        "banketbakker",
        "banketbakkerij",
        "warme bakker",
    },
    # === NEW DOMAINS (Expanded Coverage) ===
    "pharmacy": {
        "pharmacy",
        "pharmacies",
        "drugstore",
        "chemist",
        "apotheek",
        "apotheker",
        "apothekers",
        "pharmacie",
        "pharmacien",
        "drogist",
        "drogisterij",
    },
    "gym": {
        "gym",
        "gyms",
        "fitness",
        "fitness center",
        "fitness centre",
        "sports center",
        "sports centre",
        "health club",
        "sportclub",
        "sport club",
        "fitnessclub",
        "fitness club",
    },
    "lawyer": {
        "lawyer",
        "lawyers",
        "attorney",
        "attorneys",
        "solicitor",
        "solicitors",
        "advocate",
        "advocates",
        "barrister",
        "legal",
        "advocaat",
        "advocaten",
        "advocatenkantoor",
        "avocat",
        "jurist",
    },
    "accountant": {
        "accountant",
        "accountants",
        "accounting",
        "bookkeeper",
        "bookkeeping",
        "boekhouder",
        "boekhouders",
        "boekhouding",
        "boekhoudkantoor",
        "comptable",
        "fiduciaire",
    },
    "doctor": {
        "doctor",
        "doctors",
        "physician",
        "physicians",
        "medical",
        "clinic",
        "healthcare",
        "huisarts",
        "huisartsen",
        "dokter",
        "dokters",
        "geneesheer",
        "geneeskunde",
        "medecin",
        "cabinet medical",
    },
    "cafe": {
        "cafe",
        "cafes",
        "coffee shop",
        "coffee bar",
        "cafeteria",
        "coffeehouse",
        "koffie",
        "koffiehuis",
        "koffiebar",
        "cafetaria",
    },
    "hotel": {
        "hotel",
        "hotels",
        "motel",
        "guesthouse",
        "guest house",
        "bed and breakfast",
        "bnb",
        "b&b",
        "accommodation",
        "hostel",
        "inn",
    },
    "construction": {
        "construction",
        "contractor",
        "builders",
        "building",
        "bouw",
        "aannemer",
        "aannemers",
        "bouwer",
        "bouwbedrijf",
        "construction company",
        "general contractor",
    },
    "electrician": {
        "electrician",
        "electricians",
        "electrical",
        "electrical contractor",
        "elektricien",
        "elektriciens",
        "elektro",
        "elektriciteit",
        "electriciteitswerken",
    },
    "painter": {
        "painter",
        "painters",
        "painting",
        "decorator",
        "decorators",
        "schilder",
        "schilders",
        "schilderwerken",
        "schildersbedrijf",
        "peintre",
    },
}


DOMAIN_HINT_CODES: dict[str, list[str]] = {
    "it": ["62100", "62200", "62900", "63100"],
    "restaurant": ["56101", "56102"],
    "pita": ["56101", "56102", "56103", "56290"],  # Restaurants, cafes, fast food
    "barber": ["96021"],
    "dentist": ["86230"],
    "plumber": ["43221"],
    "bakery": ["10711", "10712", "10720", "47241"],
    # === NEW DOMAINS ===
    "pharmacy": ["47731", "47732", "21200"],  # Dispensing chemists, pharmaceutical goods
    "gym": ["93130", "93120"],  # Fitness facilities, sports clubs
    "lawyer": ["69101", "69102", "69109"],  # Legal activities
    "accountant": ["69201", "69202", "69203"],  # Accounting, bookkeeping, tax consultancy
    "doctor": ["86210", "86220", "86230"],  # General medical practice, specialists
    "cafe": ["56103", "56301"],  # Cafes, beverage serving
    "hotel": ["55101", "55102", "55103", "55201", "55202"],  # Hotels, hostels, B&Bs
    "construction": ["41101", "41102", "41201", "42910"],  # Construction of buildings
    "electrician": ["43211", "43212", "43220"],  # Electrical installation
    "painter": ["43310", "43341"],  # Painting, glazing, plastering
}

DOMAIN_CODE_PREFIX_FILTERS: dict[str, tuple[str, ...]] = {
    "it": ("621", "622", "629", "6310"),
    "restaurant": ("56",),
    "pita": ("56",),  # Food and beverage service activities
    "barber": ("9602",),
    "dentist": ("8623",),
    "plumber": ("4322",),
    "bakery": ("1071", "1072", "4724"),
    # === NEW DOMAINS ===
    "pharmacy": ("4773", "2120"),
    "gym": ("931",),
    "lawyer": ("691",),
    "accountant": ("692",),
    "doctor": ("862", "869"),
    "cafe": ("56",),
    "hotel": ("55",),
    "construction": ("41", "42", "43"),
    "electrician": ("432",),
    "painter": ("433",),
}

DOMAIN_ALLOWED_CODES_EXACT: dict[str, set[str]] = {
    # Current verified KBO-backed IT segment. The older 62010/62020/62030/62090/63110/63120
    # software set does not exist in the Brussels dataset used for the current demo/story.
    "it": {"62100", "62200", "62900", "63100"},
}

GENERIC_ACTIVITY_TERMS: set[str] = {
    "activity",
    "activities",
    "business",
    "businesses",
    "company",
    "companies",
    "enterprise",
    "enterprises",
    "firm",
    "firms",
    "industry",
    "industries",
    "service",
    "services",
}


def _resolve_domain_key(keyword_normalized: str) -> str | None:
    for domain, aliases in DOMAIN_SYNONYMS.items():
        if keyword_normalized in aliases:
            return domain
    keyword_tokens = keyword_normalized.split()
    for token in keyword_tokens:
        for domain, aliases in DOMAIN_SYNONYMS.items():
            if token in aliases:
                return domain
    return None


def _expand_search_terms(keyword_normalized: str) -> set[str]:
    terms = {keyword_normalized}
    for token in keyword_normalized.split():
        if len(token) > 2:
            terms.add(token)
            if token.endswith("s") and len(token) > 4:
                terms.add(token[:-1])
            if token.endswith("ies") and len(token) > 5:
                terms.add(f"{token[:-3]}y")

    domain_key = _resolve_domain_key(keyword_normalized)
    if domain_key:
        terms.update(DOMAIN_SYNONYMS[domain_key])
    return {term for term in terms if term}


def _is_overly_generic_keyword(keyword_normalized: str, domain_key: str | None) -> bool:
    if domain_key:
        return False
    tokens = [token for token in keyword_normalized.split() if token]
    if not tokens:
        return True
    return all(token in GENERIC_ACTIVITY_TERMS for token in tokens)


def _score_nace_description(
    keyword_normalized: str, expanded_terms: set[str], description_normalized: str
) -> int:
    score = 0
    if not description_normalized:
        return score

    if re.search(rf"\b{re.escape(keyword_normalized)}\b", description_normalized):
        score += 8

    for term in expanded_terms:
        if term in GENERIC_ACTIVITY_TERMS:
            continue
        if len(term) <= 2:
            # Avoid false positives like "IT" matching "sanITary".
            if re.search(rf"\b{re.escape(term)}\b", description_normalized):
                score += 6
            continue

        if re.search(rf"\b{re.escape(term)}\b", description_normalized):
            score += 4
        elif len(term) >= 4 and re.search(rf"\b{re.escape(term)}", description_normalized):
            score += 2

    return score


def _get_nace_codes_from_keyword(keyword: str) -> list[str]:
    """Find NACE codes for an activity keyword using enriched KBO data."""
    keyword_normalized = _normalize_text(keyword)
    if not keyword_normalized:
        return []

    domain_key = _resolve_domain_key(keyword_normalized)
    if _is_overly_generic_keyword(keyword_normalized, domain_key):
        return []

    hint_codes = list(DOMAIN_HINT_CODES.get(domain_key or "", []))
    allowed_prefixes = DOMAIN_CODE_PREFIX_FILTERS.get(domain_key or "")
    allowed_codes_exact = DOMAIN_ALLOWED_CODES_EXACT.get(domain_key or "")
    expanded_terms = _expand_search_terms(keyword_normalized)

    scored: list[tuple[int, str]] = []
    for code, description in NACE_CATALOG.items():
        score = _score_nace_description(
            keyword_normalized, expanded_terms, _normalize_text(description)
        )
        if score > 0:
            scored.append((score, code))

    scored.sort(key=lambda item: (-item[0], item[1]))

    matches: list[str] = []
    for code in hint_codes:
        if code not in matches:
            matches.append(code)

    for score, code in scored:
        if score < 4:
            continue
        if allowed_codes_exact and code not in allowed_codes_exact:
            continue
        if allowed_prefixes and not code.startswith(allowed_prefixes):
            continue
        if code not in matches:
            matches.append(code)
        if len(matches) >= 12:
            break

    return matches[:12]


@tool
def lookup_nace_code(keyword: str) -> list[str]:
    """Find NACE codes for an industry or activity.

    Args:
        keyword: Industry name like 'IT', 'Construction', 'Restaurant'.

    Returns:
        List of relevant NACE codes (max 12 best matches).

    Example:
        Input: 'IT' -> Returns ['62100', '62200', '62900', '63100']
    """
    return _get_nace_codes_from_keyword(keyword)


@tool
def lookup_juridical_code(keyword: str) -> list[str]:
    """Find Juridical Form codes for a Belgian legal entity type.

    Args:
        keyword: Keyword like 'BV', 'NV', 'VZW'.

    Returns:
        List of matching juridical form codes.

    Example:
        Input: 'NV' -> Returns ['014']
    """
    keyword_lower = keyword.lower()
    return [
        code
        for code, description in JURIDICAL_CODES.items()
        if keyword_lower in description.lower()
    ]


# Re-export for use by other modules
__all__ = [
    "lookup_nace_code",
    "lookup_juridical_code",
    "_get_nace_codes_from_keyword",
    "NACE_CATALOG",
    "JURIDICAL_CODES",
    "DOMAIN_SYNONYMS",
    "DOMAIN_HINT_CODES",
    "DOMAIN_CODE_PREFIX_FILTERS",
    "DOMAIN_ALLOWED_CODES_EXACT",
    "GENERIC_ACTIVITY_TERMS",
]
