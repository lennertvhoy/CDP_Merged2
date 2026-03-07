"""Multi-turn conversational user-story integration coverage."""

from __future__ import annotations

import os

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from tests.integration.helpers.assertions import (
    assert_error_recovery_happened,
    assert_expected_tools,
    assert_protocol_invariants,
    assert_session_identity,
    assert_turn_indexing,
)
from tests.integration.helpers.conversation_driver import ConversationDriver, TurnSpec

INTEGRATION = os.getenv("INTEGRATION_TESTS", "0") == "1"
pytestmark = pytest.mark.integration


@tool
def lookup_nace_code_mock(keyword: str) -> list[str]:
    """Deterministic NACE resolver used for harness stability."""
    mapping = {"it": ["62010", "62020"], "restaurant": ["56101"]}
    return mapping.get(keyword.lower(), ["99999"])


@tool
async def search_profiles_mock(
    keywords: str | None = None,
    city: str | None = None,
    status: str | None = "AC",
) -> str:
    """Deterministic profile lookup for multi-turn stories."""
    key = keywords or "any"
    city_label = city or "any-city"
    return f"found_profiles key={key} city={city_label} status={status}"


@tool
async def create_segment_mock(name: str, condition: str) -> str:
    """Deterministic segment creation stub."""
    return f"segment_created name={name} condition={condition} count=2"


@tool
async def push_to_resend_mock(segment_id: str) -> str:
    """Deterministic outbound push stub."""
    return f"pushed_to_resend segment_id={segment_id} count=2"


@tool
async def create_data_artifact_mock(
    title: str,
    artifact_type: str,
    output_format: str = "markdown",
    use_last_search: bool = False,
) -> str:
    """Deterministic local artifact generation stub."""
    return (
        f"artifact_created title={title} type={artifact_type} format={output_format} "
        f"use_last_search={use_last_search}"
    )


@tool
async def recoverable_lookup(keyword: str) -> str:
    """Tool that can fail once to exercise fallback + recovery path."""
    if keyword == "fail":
        raise RuntimeError("forced failure for recovery story")
    return f"lookup_ok keyword={keyword}"


class DeterministicStoryModel:
    """Deterministic tool-calling model that simulates realistic turn behavior."""

    async def ainvoke(self, messages: list[BaseMessage]) -> AIMessage:
        last = messages[-1]
        human_messages = [m for m in messages if isinstance(m, HumanMessage)]
        last_human = human_messages[-1].content.lower() if human_messages else ""

        if isinstance(last, ToolMessage):
            if last.name == "lookup_nace_code_mock":
                return AIMessage(content=f"NACE resolved: {last.content}")

            if last.name == "search_profiles_mock":
                return AIMessage(content=f"Search complete: {last.content}")

            if last.name == "create_segment_mock":
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "push_to_resend_mock",
                            "args": {"segment_id": "it-gent"},
                            "id": "call-push-1",
                            "type": "tool_call",
                        }
                    ],
                )

            if last.name == "push_to_resend_mock":
                return AIMessage(content=f"Tool-heavy flow finished: {last.content}")

            if last.name == "create_data_artifact_mock":
                return AIMessage(content=f"Artifact ready: {last.content}")

            if last.name == "recoverable_lookup":
                if getattr(last, "status", None) == "error":
                    return AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "recoverable_lookup",
                                "args": {"keyword": "it"},
                                "id": "call-recover-2",
                                "type": "tool_call",
                            }
                        ],
                    )
                return AIMessage(content=f"Recovered successfully: {last.content}")

            return AIMessage(content=f"Processed tool output: {last.content}")

        if "bonjour" in last_human:
            return AIMessage(content="Réponse française confirmée pour ce tour.")
        if "hallo" in last_human:
            return AIMessage(content="Nederlandse bevestiging voor deze beurt.")

        if "create the segment" in last_human:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "create_segment_mock",
                        "args": {"name": "it-gent", "condition": 'traits.city="Gent"'},
                        "id": "call-seg-1",
                        "type": "tool_call",
                    }
                ],
            )

        if "spreadsheet" in last_human or "artifact" in last_human or "report" in last_human:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "create_data_artifact_mock",
                        "args": {
                            "title": "it-gent-report",
                            "artifact_type": "search_results",
                            "output_format": "csv",
                            "use_last_search": True,
                        },
                        "id": "call-artifact-1",
                        "type": "tool_call",
                    }
                ],
            )

        if "follow-up" in last_human or "those companies" in last_human:
            previous_context = " ".join(m.content.lower() for m in human_messages[:-1])
            city = "gent" if "gent" in previous_context else "brussel"
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "search_profiles_mock",
                        "args": {"city": city, "keywords": "it", "status": "AC"},
                        "id": "call-search-followup",
                        "type": "tool_call",
                    }
                ],
            )

        if "tool-heavy" in last_human:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_nace_code_mock",
                        "args": {"keyword": "IT"},
                        "id": "call-nace-1",
                        "type": "tool_call",
                    }
                ],
            )

        if "trigger failure" in last_human:
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "recoverable_lookup",
                        "args": {"keyword": "fail"},
                        "id": "call-recover-1",
                        "type": "tool_call",
                    }
                ],
            )

        return AIMessage(content="Acknowledged and remembered for the same identity session.")


def _stable_driver(*, thread_id: str) -> ConversationDriver:
    return ConversationDriver(
        thread_id=thread_id,
        agent_model=DeterministicStoryModel(),
        bound_tools=[
            lookup_nace_code_mock,
            search_profiles_mock,
            create_segment_mock,
            push_to_resend_mock,
            create_data_artifact_mock,
            recoverable_lookup,
        ],
    )


class TestMultiTurnUserStoriesStableHarness:
    @pytest.mark.asyncio
    async def test_user_stories_in_one_thread(self):
        # Why it matters: validates realistic multi-turn progression with memory continuity.
        driver = _stable_driver(thread_id="it-thread-stable-user-stories")
        specs = [
            TurnSpec(user_text="Find IT companies in Gent."),
            TurnSpec(user_text="Bonjour, can you answer in French now?", expect_language="fr"),
            TurnSpec(user_text="Hallo, schakel nu naar Nederlands.", expect_language="nl"),
            TurnSpec(
                user_text="Follow-up: use those companies and narrow to active only.",
                expect_tools=["search_profiles_mock"],
            ),
            TurnSpec(
                user_text="Create a spreadsheet artifact for those companies.",
                expect_tools=["create_data_artifact_mock"],
            ),
            TurnSpec(
                user_text="Run a tool-heavy plan for this context.",
                expect_tools=["lookup_nace_code_mock"],
            ),
            TurnSpec(
                user_text="Create the segment and continue the tool-heavy flow.",
                expect_tools=["create_segment_mock", "push_to_resend_mock"],
            ),
            TurnSpec(
                user_text="Trigger failure and recover in the same turn.",
                expect_tools=["recoverable_lookup"],
                expect_error_recovery=True,
            ),
            TurnSpec(user_text="Identity check: what do you remember about this ongoing thread?"),
        ]

        results = await driver.run_conversation(specs)
        snapshot_path = driver.persist_snapshot("test_user_stories_in_one_thread", results)

        assert_turn_indexing(results)
        assert_session_identity(results)

        for result, spec in zip(results, specs, strict=True):
            assert_protocol_invariants(result, expect_tools=bool(spec.expect_tools))
            if spec.expect_tools:
                assert_expected_tools(result, spec.expect_tools)
            if spec.expect_error_recovery:
                assert_error_recovery_happened(result)

        assert results[1].language == "fr"
        assert results[2].language == "nl"
        assert "search_profiles_mock" in {c.get("name") for c in results[3].tool_calls}
        assert "tests/integration/snapshots/test_user_stories_in_one_thread" in snapshot_path

    @pytest.mark.asyncio
    async def test_identity_consistency_over_turns(self):
        # Why it matters: guards stable identity continuity for personalization and safety.
        driver = _stable_driver(thread_id="it-thread-stable-identity")
        results = await driver.run_conversation(
            [
                TurnSpec(user_text="Start session for identity continuity."),
                TurnSpec(
                    user_text="those companies follow-up for identity memory",
                    expect_tools=["search_profiles_mock"],
                ),
                TurnSpec(user_text="Identity check in same thread."),
            ]
        )

        assert_turn_indexing(results)
        assert_session_identity(results)
        assert_expected_tools(results[1], ["search_profiles_mock"])


@pytest.mark.skipif(not INTEGRATION, reason="Requires INTEGRATION_TESTS=1 and real services")
class TestTrueEndToEndPath:
    @pytest.mark.asyncio
    async def test_real_runtime_path_single_turn(self):
        # Why it matters: preserves at least one real E2E path without local tool/model stubs.
        driver = ConversationDriver()
        results = await driver.run_conversation(
            [TurnSpec(user_text="Hello, summarize your capabilities briefly.")]
        )
        driver.persist_snapshot("test_real_runtime_path_single_turn", results)

        assert len(results) == 1
        assert_protocol_invariants(results[0])
