"""Formatting helpers for the Chainlit user experience layer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

TOTAL_KBO_COMPANIES: Final[int] = 1_940_603
ENRICHMENT_CHUNK_SIZE: Final[int] = 10_000
DEFAULT_CHAT_PROFILE: Final[str] = "marketing_manager"


@dataclass(frozen=True)
class ProfileCopy:
    """Copy blocks that define the voice and focus of a chat profile."""

    name: str
    display_name: str
    summary: str
    focus_line: str
    prompts: tuple[str, str, str]


@dataclass(frozen=True)
class StatusCard:
    """Compact status signal rendered in markdown tables."""

    signal: str
    value: str
    detail: str


PROFILE_COPY: dict[str, ProfileCopy] = {
    "marketing_manager": ProfileCopy(
        name="marketing_manager",
        display_name="Audience Strategist",
        summary=(
            "Audience design, campaign planning, and activation handoff for Belgian company data."
        ),
        focus_line="Reachable segments, coverage signals, and launch-ready activation lists.",
        prompts=(
            "Find software companies in Gent with a website and email address",
            "Create a segment of HR consultancies in Vlaams-Brabant with verified contact data",
            "Show the best outreach-ready companies in Wallonie by sector and contact coverage",
        ),
    ),
    "sales_rep": ProfileCopy(
        name="sales_rep",
        display_name="Account Executive",
        summary="Pipeline-building guidance and account prioritization with clear Belgian market context.",
        focus_line="Named accounts, regional whitespace, and fast qualification.",
        prompts=(
            "Find manufacturers in Antwerpen with a website but no segment assigned yet",
            "List logistics companies in Brussel with direct contact data and a strong profile match",
            "Show me KBO-ready prospects in Oost-Vlaanderen for outbound outreach",
        ),
    ),
    "data_analyst": ProfileCopy(
        name="data_analyst",
        display_name="Insights Analyst",
        summary="Coverage diagnostics, market sizing, and deterministic customer-intelligence analysis.",
        focus_line="Counts, readiness gaps, and explainable filters.",
        prompts=(
            "How many construction companies in Belgium have both email and website data?",
            "Compare enrichment readiness across Vlaams-Brabant, Antwerpen, and Liège",
            "Show the top NACE groups for companies still pending enrichment",
        ),
    ),
    "platform_admin": ProfileCopy(
        name="platform_admin",
        display_name="Platform Operator",
        summary="Operational oversight for the PostgreSQL-first query plane and downstream activation runtime.",
        focus_line="Runtime health, release confidence, and safe operational follow-through.",
        prompts=(
            "Summarize the current query plane, activation runtime, and enrichment monitor status",
            "Show the current enrichment progress and where the evidence comes from",
            "Which follow-up checks matter before projecting a new segment downstream?",
        ),
    ),
}


def get_profile_copy(profile_name: str | None) -> ProfileCopy:
    """Return profile-specific copy with a safe default."""
    return PROFILE_COPY.get(
        profile_name or DEFAULT_CHAT_PROFILE, PROFILE_COPY[DEFAULT_CHAT_PROFILE]
    )


def build_status_cards(repo_root: Path) -> list[StatusCard]:
    """Build a small set of status cards for the welcome and status messages."""
    return [
        StatusCard(
            signal="Truth layer",
            value="PostgreSQL-first",
            detail="Counts, search, and analytics are anchored in the canonical intelligence store.",
        ),
        StatusCard(
            signal="Activation runtime",
            value="Tracardi downstream",
            detail="Segment projection, workflows, and outbound actions remain operational layers.",
        ),
        _build_enrichment_card(repo_root),
    ]


def _build_enrichment_card(repo_root: Path) -> StatusCard:
    log_dir = repo_root / "logs" / "enrichment"
    log_files = sorted(log_dir.glob("cbe_continuous_*.log"), key=lambda path: path.stat().st_mtime)

    if not log_files:
        return StatusCard(
            signal="Enrichment monitor",
            value="No local chunk log detected",
            detail="Progress will appear here when the chunk runner writes a cbe_continuous log.",
        )

    latest_log = log_files[-1]
    content = latest_log.read_text(encoding="utf-8", errors="ignore")
    chunk_count = len(re.findall(r"ENRICHMENT COMPLETE", content))
    updated_at = datetime.fromtimestamp(latest_log.stat().st_mtime).strftime("%Y-%m-%d %H:%M")

    if chunk_count == 0:
        return StatusCard(
            signal="Enrichment monitor",
            value="Active, waiting for the first completed chunk",
            detail=f"Watching {latest_log.name}; last update {updated_at}.",
        )

    processed = min(chunk_count * ENRICHMENT_CHUNK_SIZE, TOTAL_KBO_COMPANIES)
    progress = processed / TOTAL_KBO_COMPANIES * 100
    return StatusCard(
        signal="Enrichment monitor",
        value=f"{chunk_count} chunks observed (~{progress:.1f}%)",
        detail=f"Chunk-based reading from {latest_log.name}; last update {updated_at}.",
    )


def build_status_markdown(status_cards: list[StatusCard]) -> str:
    """Render status cards as a markdown table."""
    rows = "\n".join(f"| {card.signal} | {card.value} | {card.detail} |" for card in status_cards)
    return "\n".join(
        [
            "### System Snapshot",
            "| Signal | Status | Detail |",
            "| --- | --- | --- |",
            rows,
        ]
    )


def build_status_summary_markdown(status_cards: list[StatusCard]) -> str:
    """Render a compact status summary for the launcher welcome."""
    summary = " • ".join(f"{card.signal}: {card.value}" for card in status_cards)
    return f"**Live signals:** {summary}"


def build_welcome_markdown(profile_name: str | None, status_cards: list[StatusCard]) -> str:
    """Render the primary welcome message."""
    profile = get_profile_copy(profile_name)

    return "\n".join(
        [
            "![CDP AI Assistant](/public/brand-wordmark.svg)",
            "",
            "# Belgian customer intelligence",
            "",
            f"**{profile.display_name}:** {profile.focus_line}",
            "",
            build_status_summary_markdown(status_cards),
            "",
            f"**Try first:** `{profile.prompts[0]}`",
        ]
    )


def build_action_markdown(
    action_name: str, profile_name: str | None, status_cards: list[StatusCard]
) -> str:
    """Render markdown for quick-action follow-up responses."""
    profile = get_profile_copy(profile_name)

    if action_name == "ui_search_companies":
        examples = "\n".join(
            [
                "- `Find IT services companies in Leuven with email and website data`",
                "- `List logistics companies in Gent that are still pending enrichment`",
                "- `Show high-confidence prospects in Wallonie for outbound outreach`",
            ]
        )
        return "\n".join(
            [
                "### Company search playbook",
                f"Use the **{profile.display_name}** profile when you need market filtering with Belgian context.",
                "",
                "- Start with geography, sector, and reachability constraints.",
                "- Ask for counts first when you want a market-size check.",
                "- Ask for KBO, VAT, province, or enrichment status when you need export-ready detail.",
                "",
                "#### Suggested prompts",
                examples,
            ]
        )

    if action_name == "ui_create_segment":
        examples = "\n".join(
            [
                "- `Create a segment of hospitality groups in Antwerpen with valid websites and email`",
                "- `Preview a segment for HR firms in Vlaams-Brabant before activating it`",
                "- `Show me the companies that would land in a Wallonie tech outreach segment`",
            ]
        )
        return "\n".join(
            [
                "### Segment design playbook",
                "Keep the targeting logic explicit and ask for a preview before downstream activation.",
                "",
                "- Describe the audience in business language.",
                "- Add region, NACE, and contactability rules together.",
                "- Confirm the result set before projecting it into Tracardi or an email channel.",
                "",
                "#### Suggested prompts",
                examples,
            ]
        )

    if action_name == "ui_view_analytics":
        examples = "\n".join(
            [
                "- `Compare email coverage for Brussels, Antwerpen, and Liège`",
                "- `Show the top NACE groups still blocked by missing enrichment`",
                "- `Summarize which provinces are most campaign-ready right now`",
            ]
        )
        return "\n".join(
            [
                "### Analytics playbook",
                "Use this lane for deterministic counts, coverage diagnostics, and readiness checks.",
                "",
                "- Ask for counts, comparisons, and top lists rather than generic summaries.",
                "- Separate analytical truth from activation workflows when interpreting results.",
                "- Tie every operational claim back to the freshest evidence you need.",
                "",
                "#### Suggested prompts",
                examples,
            ]
        )

    if action_name == "push_to_resend":
        return "\n".join(
            [
                "### Activation handoff",
                "Validate the segment first, then move downstream into delivery tooling.",
                "",
                "- PostgreSQL stays the analytical truth layer.",
                "- Tracardi and email providers receive only the activation slice they need.",
                "- Ask for a preview or export before sending a campaign audience downstream.",
            ]
        )

    return "\n".join(
        [
            "### Live status",
            build_status_markdown(status_cards),
            "",
            "This snapshot is derived from the local repo state and the latest enrichment chunk log.",
        ]
    )
