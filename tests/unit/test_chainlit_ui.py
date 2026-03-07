from pathlib import Path

from src.ui.formatters import build_status_cards, build_welcome_markdown
from tests.unit.chainlit_test_harness import load_modules_with_fake_chainlit


def test_build_status_cards_reads_chunk_log(tmp_path: Path):
    log_dir = tmp_path / "logs" / "enrichment"
    log_dir.mkdir(parents=True)
    (log_dir / "cbe_continuous_test.log").write_text(
        "ENRICHMENT COMPLETE\nnoise\nENRICHMENT COMPLETE\n",
        encoding="utf-8",
    )

    cards = build_status_cards(tmp_path)

    enrichment = next(card for card in cards if card.signal == "Enrichment monitor")
    assert enrichment.value == "2 chunks observed (~1.0%)"
    assert "cbe_continuous_test.log" in enrichment.detail


def test_build_chat_profiles_exposes_expected_roles(monkeypatch):
    modules, _, _ = load_modules_with_fake_chainlit(monkeypatch, "src.ui.components")

    profiles = modules["src.ui.components"].build_chat_profiles()

    assert [profile.name for profile in profiles] == [
        "marketing_manager",
        "sales_rep",
        "data_analyst",
        "platform_admin",
    ]
    assert sum(1 for profile in profiles if profile.default) == 1


def test_build_starters_defaults_to_marketing_profile(monkeypatch):
    modules, _, _ = load_modules_with_fake_chainlit(monkeypatch, "src.ui.components")

    starters = modules["src.ui.components"].build_starters(None)

    assert len(starters) == 3
    assert starters[0].label == "Reachable Tech"


def test_welcome_actions_and_markdown_include_profile_context(tmp_path: Path, monkeypatch):
    modules, _, _ = load_modules_with_fake_chainlit(monkeypatch, "src.ui.actions")

    cards = build_status_cards(tmp_path)
    welcome = build_welcome_markdown("data_analyst", cards)
    actions = modules["src.ui.actions"].build_welcome_actions("data_analyst")

    assert "Insights Analyst" in welcome
    assert "Live signals" in welcome
    assert "Try first:" in welcome
    assert "Workspace:" not in welcome
    assert "Use the quick actions below" not in welcome
    assert [action.name for action in actions] == [
        "ui_search_companies",
        "ui_create_segment",
        "ui_view_analytics",
        "ui_show_status",
    ]
