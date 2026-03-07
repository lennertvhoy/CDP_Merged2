"""Reusable Chainlit components for profiles and starter prompts."""

from __future__ import annotations

import chainlit as cl

from src.ui.formatters import DEFAULT_CHAT_PROFILE, get_profile_copy


def build_chat_profiles() -> list[cl.ChatProfile]:
    """Return the role-based profiles shown in the Chainlit launcher."""
    profiles = [
        (
            "marketing_manager",
            "Plan campaigns, build audiences, and prepare downstream activation.",
        ),
        (
            "sales_rep",
            "Surface Belgian accounts quickly with region and reachability cues.",
        ),
        (
            "data_analyst",
            "Audit counts, enrichment coverage, and market structure with deterministic queries.",
        ),
        (
            "platform_admin",
            "Inspect query-plane status, activation boundaries, and operational follow-up.",
        ),
    ]

    chat_profiles: list[cl.ChatProfile] = []
    for name, description in profiles:
        profile = get_profile_copy(name)
        chat_profiles.append(
            cl.ChatProfile(
                name=name,
                display_name=profile.display_name,
                markdown_description=description,
                default=name == DEFAULT_CHAT_PROFILE,
                starters=build_starters(name),
            )
        )

    return chat_profiles


def build_starters(profile_name: str | None) -> list[cl.Starter]:
    """Return profile-specific starter prompts."""
    profile = get_profile_copy(profile_name)
    starter_map = {
        "marketing_manager": [
            cl.Starter(
                label="Reachable Tech",
                message="Find software companies in Gent with a website and email address",
                icon="/public/logo.svg",
            ),
            cl.Starter(
                label="Segment Preview",
                message="Preview a segment of HR consultancies in Vlaams-Brabant with verified contact data",
                icon="/public/logo.svg",
            ),
            cl.Starter(
                label="Campaign Readiness",
                message="Which provinces are most campaign-ready based on current enrichment coverage?",
                icon="/public/logo.svg",
            ),
        ],
        "sales_rep": [
            cl.Starter(
                label="Leuven Prospects",
                message="Find manufacturers in Leuven with contact data and website coverage",
                icon="/public/logo.svg",
            ),
            cl.Starter(
                label="Wallonie Leads",
                message="Show outbound-ready prospects in Wallonie with KBO and VAT details",
                icon="/public/logo.svg",
            ),
            cl.Starter(
                label="Brussels Accounts",
                message="List logistics companies in Brussels with a strong qualification signal",
                icon="/public/logo.svg",
            ),
        ],
        "data_analyst": [
            cl.Starter(
                label="Coverage Gap",
                message="Compare email and website coverage across Antwerpen, Brussel, and Liège",
                icon="/public/logo.svg",
            ),
            cl.Starter(
                label="Top NACE",
                message="Show the top NACE groups still pending enrichment",
                icon="/public/logo.svg",
            ),
            cl.Starter(
                label="Regional Counts",
                message="How many construction companies in Belgium have both email and website data?",
                icon="/public/logo.svg",
            ),
        ],
        "platform_admin": [
            cl.Starter(
                label="System Snapshot",
                message="Summarize the current query plane, activation runtime, and enrichment monitor status",
                icon="/public/logo.svg",
            ),
            cl.Starter(
                label="Evidence Check",
                message="Show the current enrichment progress and where the evidence comes from",
                icon="/public/logo.svg",
            ),
            cl.Starter(
                label="Safe Activation",
                message="Which validation steps matter before projecting a new segment downstream?",
                icon="/public/logo.svg",
            ),
        ],
    }
    return starter_map.get(profile.name, starter_map[DEFAULT_CHAT_PROFILE])
