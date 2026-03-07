"""Reusable conversation driver for integration multi-turn stories."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from src.graph.nodes import detect_language
from src.graph.workflow import compile_workflow


@dataclass
class TurnSpec:
    user_text: str
    expect_tools: list[str] | None = None
    expect_language: str | None = None
    expect_error_recovery: bool = False
    notes: str | None = None


@dataclass
class TurnResult:
    turn_index: int
    user_text: str
    final_answer: str | None
    tool_calls: list[dict[str, Any]]
    node_trace: list[str]
    language: str | None
    profile_id: str | None
    thread_id: str
    raw_chunks: list[dict[str, Any]]


class ConversationDriver:
    """Run deterministic or real runtime conversation turns and collect diagnostics."""

    def __init__(
        self,
        *,
        thread_id: str | None = None,
        profile_id: str | None = None,
        agent_model: Any | None = None,
        bound_tools: list[Any] | None = None,
    ) -> None:
        self.thread_id = thread_id or "integration-thread"
        self.profile_id = profile_id or f"profile-{self.thread_id}"
        self.agent_model = agent_model
        self.bound_tools = bound_tools or []
        self._history: list[BaseMessage] = []
        self._turn_counter = 0
        self._tool_by_name = {tool_obj.name: tool_obj for tool_obj in self.bound_tools}

        self._workflow = None
        if self.agent_model is None:
            self._workflow = compile_workflow(checkpointer=MemorySaver())

    async def run_turn(self, spec: TurnSpec) -> TurnResult:
        self._turn_counter += 1
        if self.agent_model is not None:
            return await self._run_turn_harness(spec)
        return await self._run_turn_real_runtime(spec)

    async def run_conversation(self, specs: list[TurnSpec]) -> list[TurnResult]:
        return [await self.run_turn(spec) for spec in specs]

    def persist_snapshot(self, test_name: str, results: list[TurnResult]) -> str:
        snapshot_dir = Path(__file__).resolve().parents[1] / "snapshots" / test_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / f"{self.thread_id}.json"

        payload = {
            "thread_id": self.thread_id,
            "profile_id": self.profile_id,
            "turn_count": len(results),
            "results": [asdict(result) for result in results],
        }
        snapshot_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return str(snapshot_path)

    async def _run_turn_harness(self, spec: TurnSpec) -> TurnResult:
        user_message = HumanMessage(content=spec.user_text)
        self._history.append(user_message)

        language = detect_language(spec.user_text)
        node_trace = ["router"]
        raw_chunks: list[dict[str, Any]] = [{"node": "router", "language": language}]
        tool_calls: list[dict[str, Any]] = []

        ai_message = await self.agent_model.ainvoke(self._history)
        guard = 0
        while True:
            guard += 1
            if guard > 16:
                raise RuntimeError("Exceeded max tool-call loop depth in harness mode.")

            node_trace.append("agent")
            raw_chunks.append({"node": "agent", "message": self._serialize_message(ai_message)})
            self._history.append(ai_message)

            pending_calls = list(getattr(ai_message, "tool_calls", []) or [])
            if not pending_calls:
                final_answer = (
                    ai_message.content
                    if isinstance(ai_message.content, str)
                    else str(ai_message.content)
                )
                return TurnResult(
                    turn_index=self._turn_counter,
                    user_text=spec.user_text,
                    final_answer=final_answer,
                    tool_calls=tool_calls,
                    node_trace=node_trace,
                    language=language,
                    profile_id=self.profile_id,
                    thread_id=self.thread_id,
                    raw_chunks=raw_chunks,
                )

            node_trace.append("tools")
            emitted_tool_messages: list[dict[str, Any]] = []
            for call in pending_calls:
                tool_calls.append(
                    {
                        "name": call.get("name"),
                        "args": call.get("args", {}),
                        "id": call.get("id"),
                    }
                )
                tool_message = await self._execute_tool_call(call)
                self._history.append(tool_message)
                emitted_tool_messages.append(self._serialize_message(tool_message))

            raw_chunks.append({"node": "tools", "tool_messages": emitted_tool_messages})
            ai_message = await self.agent_model.ainvoke(self._history)

    async def _run_turn_real_runtime(self, spec: TurnSpec) -> TurnResult:
        if self._workflow is None:
            raise RuntimeError("Workflow is not initialized for real runtime mode.")

        inputs = {
            "messages": [HumanMessage(content=spec.user_text)],
            "language": "",
            "profile_id": self.profile_id,
        }
        config = {"configurable": {"thread_id": self.thread_id}}

        final_answer: str | None = None
        language: str | None = None
        tool_calls: list[dict[str, Any]] = []
        node_trace: list[str] = []
        raw_chunks: list[dict[str, Any]] = []

        async for chunk in self._workflow.astream(inputs, config=config):
            for node_name, node_output in chunk.items():
                node_trace.append(node_name)
                raw_chunks.append(
                    {"node": node_name, "output": self._serialize_payload(node_output)}
                )

                if node_name == "router" and isinstance(node_output, dict):
                    language = node_output.get("language") or language

                if not isinstance(node_output, dict):
                    continue

                messages = node_output.get("messages", []) or []
                if not messages:
                    continue

                last_message = messages[-1]
                if isinstance(last_message, AIMessage):
                    for call in list(getattr(last_message, "tool_calls", []) or []):
                        tool_calls.append(
                            {
                                "name": call.get("name"),
                                "args": call.get("args", {}),
                                "id": call.get("id"),
                            }
                        )
                    if last_message.content:
                        final_answer = str(last_message.content)

        if language is None:
            language = detect_language(spec.user_text)

        return TurnResult(
            turn_index=self._turn_counter,
            user_text=spec.user_text,
            final_answer=final_answer,
            tool_calls=tool_calls,
            node_trace=node_trace,
            language=language,
            profile_id=self.profile_id,
            thread_id=self.thread_id,
            raw_chunks=raw_chunks,
        )

    async def _execute_tool_call(self, call: dict[str, Any]) -> ToolMessage:
        name = str(call.get("name", ""))
        args = call.get("args", {}) or {}
        tool_call_id = str(call.get("id", name or "tool-call"))

        tool_obj = self._tool_by_name.get(name)
        if tool_obj is None:
            return ToolMessage(
                content=f"Missing tool: {name}",
                tool_call_id=tool_call_id,
                name=name,
                status="error",
            )

        try:
            if getattr(tool_obj, "coroutine", None):
                output = await tool_obj.coroutine(**args)
            elif hasattr(tool_obj, "func"):
                output = tool_obj.func(**args)
                if hasattr(output, "__await__"):
                    output = await output
            elif hasattr(tool_obj, "ainvoke"):
                output = await tool_obj.ainvoke(args)
            else:
                output = tool_obj(**args)
                if hasattr(output, "__await__"):
                    output = await output
            return ToolMessage(
                content=self._stringify(output), tool_call_id=tool_call_id, name=name
            )
        except Exception as exc:  # pragma: no cover - exercised in integration tests
            return ToolMessage(
                content=f"{type(exc).__name__}: {exc}",
                tool_call_id=tool_call_id,
                name=name,
                status="error",
            )

    def _serialize_message(self, message: BaseMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": type(message).__name__,
            "content": self._stringify(getattr(message, "content", "")),
        }
        if isinstance(message, AIMessage):
            payload["tool_calls"] = list(getattr(message, "tool_calls", []) or [])
        if isinstance(message, ToolMessage):
            payload["name"] = getattr(message, "name", None)
            payload["status"] = getattr(message, "status", None)
            payload["tool_call_id"] = getattr(message, "tool_call_id", None)
        return payload

    def _serialize_payload(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._serialize_payload(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._serialize_payload(item) for item in value]
        if isinstance(value, BaseMessage):
            return self._serialize_message(value)
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return self._stringify(value)

    def _stringify(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(value)
