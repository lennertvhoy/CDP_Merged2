"""Quick-action builders and response helpers for the Chainlit UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chainlit as cl

from src.ui.formatters import (
    DEFAULT_CHAT_PROFILE,
    build_action_markdown,
    build_status_cards,
)


@dataclass(frozen=True)
class ActionReply:
    """Structured quick-action response."""

    content: str
    actions: list[cl.Action]


def build_welcome_actions(profile_name: str | None) -> list[cl.Action]:
    """Primary quick actions shown on chat start."""
    profile = profile_name or DEFAULT_CHAT_PROFILE
    return [
        cl.Action(
            name="ui_search_companies",
            payload={"profile": profile},
            label="Find Accounts",
            tooltip="Explore company discovery prompts for Belgian KBO data.",
        ),
        cl.Action(
            name="ui_create_segment",
            payload={"profile": profile},
            label="Design Segment",
            tooltip="See how to shape and preview an audience before activation.",
        ),
        cl.Action(
            name="ui_view_analytics",
            payload={"profile": profile},
            label="Review Coverage",
            tooltip="Open coverage, counts, and readiness examples.",
        ),
        cl.Action(
            name="ui_show_status",
            payload={"profile": profile},
            label="Runtime Status",
            tooltip="Inspect the current query-plane and enrichment snapshot.",
        ),
    ]


def build_action_reply(action_name: str, profile_name: str | None, repo_root: Path) -> ActionReply:
    """Build content and follow-up actions for a quick-action callback."""
    actions = _follow_up_actions(action_name, profile_name)
    status_cards = build_status_cards(repo_root)
    content = build_action_markdown(action_name, profile_name, status_cards)
    return ActionReply(content=content, actions=actions)


def _follow_up_actions(action_name: str, profile_name: str | None) -> list[cl.Action]:
    profile = profile_name or DEFAULT_CHAT_PROFILE

    if action_name == "ui_search_companies":
        names = ["ui_create_segment", "ui_view_analytics", "ui_show_status"]
    elif action_name == "ui_create_segment":
        names = ["ui_view_analytics", "push_to_resend", "ui_show_status"]
    elif action_name == "ui_view_analytics":
        names = ["ui_search_companies", "ui_create_segment", "ui_show_status"]
    elif action_name == "push_to_resend":
        names = ["ui_create_segment", "ui_show_status"]
    else:
        names = ["ui_search_companies", "ui_create_segment", "ui_view_analytics"]

    label_map = {
        "ui_search_companies": ("Find Accounts", "Review discovery prompts and search angles."),
        "ui_create_segment": ("Design Segment", "Shape and preview a segment before activation."),
        "ui_view_analytics": ("Review Coverage", "Inspect counts, readiness, and coverage."),
        "ui_show_status": (
            "Runtime Status",
            "Refresh the local query-plane and enrichment snapshot.",
        ),
        "push_to_resend": ("Activation Handoff", "Review downstream activation guidance."),
    }

    return [
        cl.Action(
            name=name,
            payload={"profile": profile},
            label=label_map[name][0],
            tooltip=label_map[name][1],
        )
        for name in names
    ]
