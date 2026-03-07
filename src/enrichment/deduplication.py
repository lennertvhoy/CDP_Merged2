"""
Deduplication enricher for Tracardi profiles.

Identifies and merges duplicate company records using:
1. Exact KBO number match (enterprise_number) — always conclusive
2. Fuzzy company name similarity (difflib.SequenceMatcher, no extra deps)
3. Address token overlap as a secondary signal

Merge strategy:
- Keep the most-complete record (most non-empty traits fields)
- Tag duplicates: traits.is_duplicate=True, traits.duplicate_of=<winner_id>
- Tag winner: traits.duplicate_count=N

Stats reported: groups_found, duplicates_flagged, merges_performed
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from src.core.logger import get_logger
from src.enrichment.base import BaseEnricher

logger = get_logger(__name__)

# Default similarity threshold (0.0 – 1.0)
DEFAULT_THRESHOLD = 0.85

# Legal-form suffixes to strip before comparison
_LEGAL_SUFFIXES = re.compile(
    r"\b(nv|bv|bvba|cvba|vzw|vof|comm\.?v|snc|sa|asbl|sprl|srl|"
    r"one-person company|eenmanszaak|société|société anonyme|"
    r"limited|ltd|inc|gmbh)\b",
    re.IGNORECASE,
)


def _normalise_name(name: str) -> str:
    """
    Normalise a company name for fuzzy comparison.

    Steps:
    1. NFKC Unicode normalisation
    2. Lower-case
    3. Remove legal form suffixes
    4. Collapse whitespace
    5. Strip leading/trailing whitespace
    """
    if not name:
        return ""
    # Unicode normalisation
    name = unicodedata.normalize("NFKC", name)
    name = name.lower()
    # Remove punctuation except spaces
    name = re.sub(r"[\"'.,;:()\-/\\]", " ", name)
    # Strip legal suffixes
    name = _LEGAL_SUFFIXES.sub("", name)
    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _name_similarity(a: str, b: str) -> float:
    """Return SequenceMatcher ratio for two normalised names."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _address_similarity(traits_a: dict, traits_b: dict) -> float:
    """
    Simple token-overlap score for address fields.

    Uses Jaccard similarity over tokens from street + city.
    """

    def _tokens(traits: dict) -> set[str]:
        parts = [
            traits.get("street", ""),
            traits.get("city", ""),
        ]
        text = " ".join(p for p in parts if p).lower()
        return set(re.findall(r"[a-z0-9]+", text))

    a_tokens = _tokens(traits_a)
    b_tokens = _tokens(traits_b)

    if not a_tokens or not b_tokens:
        return 0.0

    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    return intersection / union if union else 0.0


def _field_count(profile: dict) -> int:
    """Count non-empty trait fields (used to choose the winner)."""
    traits = profile.get("traits", {})
    return sum(1 for v in traits.values() if v is not None and v != "" and v != [])


def _combined_score(
    kbo_match: bool,
    name_sim: float,
    addr_sim: float,
) -> float:
    """
    Combine similarity signals into a single score.

    KBO exact match is always conclusive (returns 1.0).
    Otherwise: 60% name + 40% address.
    """
    if kbo_match:
        return 1.0
    return 0.6 * name_sim + 0.4 * addr_sim


class DeduplicationEnricher(BaseEnricher):
    """
    Detect and merge duplicate company profiles.

    This enricher is batch-level: it needs the full profile set to compare.
    Override enrich_batch rather than enrich_profile for actual logic.
    enrich_profile is still required by the abstract base but is a no-op
    when called in isolation (deduplication requires pairs).
    """

    # Extra stats counters
    groups_found: int = 0
    duplicates_flagged: int = 0
    merges_performed: int = 0

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        cache_dir: str | None = "./data/cache",
        cache_file: str = "deduplication_cache.json",
    ):
        super().__init__(cache_dir=cache_dir, cache_file=cache_file)
        self.threshold = threshold
        self.groups_found = 0
        self.duplicates_flagged = 0
        self.merges_performed = 0

    def can_enrich(self, profile: dict) -> bool:
        """Every profile can participate in deduplication."""
        return True

    def start(self) -> None:
        """Reset stats including dedup-specific counters."""
        super().start()
        self.groups_found = 0
        self.duplicates_flagged = 0
        self.merges_performed = 0

    # ──────────────────────────────────────────────────────────────────────────
    # Core duplication detection
    # ──────────────────────────────────────────────────────────────────────────

    def _is_duplicate(self, profile_a: dict, profile_b: dict) -> bool:
        """Return True if two profiles are likely the same entity."""
        traits_a = profile_a.get("traits", {})
        traits_b = profile_b.get("traits", {})

        kbo_a = traits_a.get("enterprise_number", "").strip()
        kbo_b = traits_b.get("enterprise_number", "").strip()

        # Exact KBO match is conclusive
        kbo_match = bool(kbo_a and kbo_b and kbo_a == kbo_b)
        if kbo_match:
            return True

        # Fuzzy name + address
        name_a = _normalise_name(traits_a.get("name", "") or traits_a.get("company_name", ""))
        name_b = _normalise_name(traits_b.get("name", "") or traits_b.get("company_name", ""))

        name_sim = _name_similarity(name_a, name_b)
        addr_sim = _address_similarity(traits_a, traits_b)
        score = _combined_score(kbo_match=False, name_sim=name_sim, addr_sim=addr_sim)

        logger.debug(
            f"Comparing '{name_a[:30]}' vs '{name_b[:30]}': "
            f"name_sim={name_sim:.2f} addr_sim={addr_sim:.2f} score={score:.2f} "
            f"threshold={self.threshold}"
        )

        return score >= self.threshold

    def _find_duplicate_groups(self, profiles: list[dict]) -> list[list[int]]:
        """
        Find groups of duplicate profiles using union-find.

        Returns a list of groups (each group is a list of indices into `profiles`).
        Singleton groups (no duplicates) are excluded.

        Complexity: O(n²) comparisons — acceptable for batches up to ~10k profiles.
        For full 516k corpus, run in streaming sub-batches or with pre-filtering
        on city/zipcode.
        """
        n = len(profiles)
        parent = list(range(n))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            parent[find(x)] = find(y)

        for i in range(n):
            for j in range(i + 1, n):
                if find(i) != find(j) and self._is_duplicate(profiles[i], profiles[j]):
                    union(i, j)

        # Collect groups
        from collections import defaultdict

        groups: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            groups[find(i)].append(i)

        return [group for group in groups.values() if len(group) > 1]

    def _apply_merge_tags(
        self,
        profiles: list[dict],
        groups: list[list[int]],
    ) -> list[dict]:
        """
        Apply duplicate tags to profiles in-place.

        For each group:
        - Elect the winner (most non-empty traits fields).
        - Tag duplicates with is_duplicate=True and duplicate_of=<winner_id>.
        - Tag winner with duplicate_count=N.
        """
        for group in groups:
            self.groups_found += 1

            # Elect winner: profile with the most populated traits
            winner_idx = max(group, key=lambda i: _field_count(profiles[i]))
            winner = profiles[winner_idx]
            winner_id = winner.get("id", f"idx_{winner_idx}")

            duplicate_indices = [i for i in group if i != winner_idx]
            duplicate_count = len(duplicate_indices)

            # Tag winner
            if "traits" not in winner:
                winner["traits"] = {}
            winner["traits"]["duplicate_count"] = duplicate_count
            winner["traits"]["is_canonical"] = True

            # Tag duplicates
            for i in duplicate_indices:
                dup = profiles[i]
                if "traits" not in dup:
                    dup["traits"] = {}
                dup["traits"]["is_duplicate"] = True
                dup["traits"]["duplicate_of"] = winner_id
                self.duplicates_flagged += 1

            self.merges_performed += 1
            logger.info(
                f"Duplicate group: winner={winner_id}, {duplicate_count} duplicate(s) flagged"
            )

        return profiles

    # ──────────────────────────────────────────────────────────────────────────
    # BaseEnricher interface
    # ──────────────────────────────────────────────────────────────────────────

    async def enrich_profile(self, profile: dict) -> dict:
        """
        Single-profile enrichment (no-op for deduplication).

        Deduplication is inherently batch-level (see enrich_batch).
        This method is provided to satisfy the abstract base class and
        is called when enrich_batch delegates individual profiles.
        """
        # No-op: all real work is done in enrich_batch
        return profile

    async def enrich_batch(
        self,
        profiles: list[dict],
        override_concurrent: int | None = None,
    ) -> list[dict]:
        """
        Enrich a batch of profiles by detecting and tagging duplicates.

        Unlike other enrichers, deduplication is O(n²) batch-level, so we
        override enrich_batch directly instead of relying on parallel
        enrich_profile calls.
        """
        self.stats.total += len(profiles)

        if not profiles:
            return profiles

        logger.info(f"Deduplication: scanning {len(profiles)} profiles for duplicates")

        groups = self._find_duplicate_groups(profiles)
        profiles = self._apply_merge_tags(profiles, groups)

        self.stats.success += len(profiles)

        logger.info(
            f"Deduplication complete: {self.groups_found} groups, "
            f"{self.duplicates_flagged} flagged, {self.merges_performed} merges"
        )

        return profiles

    def get_dedup_stats(self) -> dict:
        """Extended stats including dedup-specific counters."""
        base = self.stats.to_dict()
        base.update(
            {
                "groups_found": self.groups_found,
                "duplicates_flagged": self.duplicates_flagged,
                "merges_performed": self.merges_performed,
                "threshold": self.threshold,
            }
        )
        return base
