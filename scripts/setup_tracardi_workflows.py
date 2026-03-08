#!/usr/bin/env python3
"""
Repair and upsert local Tracardi email workflows via the current draft API.

This replaces the earlier stale `/flow` endpoint usage with the 1.0.x
`/flow/draft` workflow format that the local GUI actually edits.
"""

from __future__ import annotations

import asyncio
import copy
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.logger import get_logger

logger = get_logger(__name__)

load_dotenv(REPO_ROOT / ".env.local")
load_dotenv(REPO_ROOT / ".env")

TRACARDI_API_URL = os.getenv("TRACARDI_API_URL", "http://localhost:8686").rstrip("/")
TRACARDI_USERNAME = os.getenv("TRACARDI_USERNAME", "admin@admin.com")
TRACARDI_PASSWORD = os.getenv("TRACARDI_PASSWORD")

if not TRACARDI_PASSWORD:
    raise RuntimeError("TRACARDI_PASSWORD must be set in the local environment")

WORKFLOW_SPECS: dict[str, dict[str, Any]] = {
    "Email Bounce Processor": {
        "description": "Handles email bounce events to mark emails as invalid and maintain list hygiene",
        "builder": "bounce",
    },
    "Email Complaint Processor": {
        "description": "Handles spam complaints by suppressing profiles and protecting sender reputation",
        "builder": "complaint",
    },
    "Email Delivery Processor": {
        "description": "Tracks email sent and delivered events to maintain email validity status",
        "builder": "delivery",
    },
    "Email Engagement Processor": {
        "description": "Processes email open and click events from Resend to track engagement scores",
        "builder": "engagement",
    },
    "High Engagement Segment": {
        "description": "Automatically assigns the High Engagement segment to engaged profiles",
        "builder": "high_engagement",
    },
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        merged = {key: copy.deepcopy(value) for key, value in base.items()}
        for key, value in patch.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    return copy.deepcopy(patch)


def _edge(source: str, source_handle: str, target: str, target_handle: str) -> dict[str, Any]:
    return {
        "id": f"{source}:{source_handle}->{target}:{target_handle}",
        "source": source,
        "sourceHandle": source_handle,
        "target": target,
        "targetHandle": target_handle,
        "type": "default",
        "data": {"name": ""},
    }


class TracardiWorkflowClient:
    def __init__(self, api_url: str, username: str, password: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.username = username
        self.password = password
        self.token: str | None = None

    async def authenticate(self) -> None:
        payload = {
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
            "scope": "",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.api_url}/user/token", data=payload)
            if response.status_code == 422:
                response = await client.post(f"{self.api_url}/user/token", json=payload)
            response.raise_for_status()
            self.token = response.json()["access_token"]

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("Client is not authenticated")
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def get_plugin_catalog(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.api_url}/flow/action/plugins",
                headers=self._headers(),
            )
            response.raise_for_status()
            grouped = response.json()["grouped"]
            return [plugin for group in grouped.values() for plugin in group]

    async def get_workflows(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.api_url}/flows/entity",
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json().get("result", [])

    async def get_draft(self, flow_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.api_url}/flow/draft/{flow_id}",
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def upsert_draft(self, draft: dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.api_url}/flow/draft?rearrange_nodes=false",
                headers=self._headers(),
                json=draft,
            )
            response.raise_for_status()


class WorkflowBuilder:
    def __init__(self, plugin_catalog: list[dict[str, Any]]) -> None:
        self.plugin_catalog = plugin_catalog

    def _plugin(self, name: str, *, class_name: str | None = None) -> dict[str, Any]:
        for plugin in self.plugin_catalog:
            plugin_body = plugin["plugin"]
            plugin_name = plugin_body["metadata"]["name"]
            plugin_class = plugin_body["spec"]["className"]
            if plugin_name == name and (class_name is None or plugin_class == class_name):
                return copy.deepcopy(plugin_body)
        raise KeyError(f"Plugin '{name}' not found in Tracardi catalog")

    def _node(
        self,
        name: str,
        *,
        position: tuple[float, float],
        class_name: str | None = None,
        init_patch: dict[str, Any] | None = None,
        start: bool | None = None,
    ) -> tuple[str, dict[str, Any]]:
        plugin = self._plugin(name, class_name=class_name)
        if start is not None:
            plugin["start"] = start
        if init_patch:
            plugin["spec"]["init"] = _deep_merge(plugin["spec"].get("init") or {}, init_patch)

        node_id = str(uuid.uuid4())
        node = {
            "id": node_id,
            "type": plugin["metadata"]["type"],
            "position": {"x": float(position[0]), "y": float(position[1])},
            "data": plugin,
        }
        return node_id, node

    def build(self, workflow_name: str) -> dict[str, Any]:
        if workflow_name not in WORKFLOW_SPECS:
            raise KeyError(f"Unsupported workflow '{workflow_name}'")
        return getattr(self, f"_build_{WORKFLOW_SPECS[workflow_name]['builder']}")()

    def _build_bounce(self) -> dict[str, Any]:
        start_id, start = self._node(
            "Start",
            class_name="StartAction",
            position=(80, 120),
            start=True,
            init_patch={"event_types": ["email.bounced"]},
        )
        copy_id, copy_node = self._node(
            "Copy data",
            position=(420, 120),
            init_patch={
                "traits": {
                    "set": {
                        "profile@traits.email_valid": "event@properties.email_valid",
                        "profile@traits.email_bounced_at": "event@properties.timestamp",
                        "profile@traits.email_bounce_type": "event@properties.bounce_type",
                        "profile@traits.email_bounce_reason": "event@properties.bounce_reason",
                    }
                }
            },
        )
        update_id, update = self._node("Update profile", position=(760, 120))
        return {
            "nodes": [start, copy_node, update],
            "edges": [
                _edge(start_id, "payload", copy_id, "payload"),
                _edge(copy_id, "payload", update_id, "payload"),
            ],
        }

    def _build_complaint(self) -> dict[str, Any]:
        start_id, start = self._node(
            "Start",
            class_name="StartAction",
            position=(80, 120),
            start=True,
            init_patch={"event_types": ["email.complained"]},
        )
        copy_id, copy_node = self._node(
            "Copy data",
            position=(420, 120),
            init_patch={
                "traits": {
                    "set": {
                        "profile@traits.email_suppressed": "event@properties.email_suppressed",
                        "profile@traits.email_suppression_reason": "event@properties.complaint_reason",
                        "profile@traits.email_suppressed_at": "event@properties.timestamp",
                    }
                }
            },
        )
        update_id, update = self._node("Update profile", position=(760, 120))
        return {
            "nodes": [start, copy_node, update],
            "edges": [
                _edge(start_id, "payload", copy_id, "payload"),
                _edge(copy_id, "payload", update_id, "payload"),
            ],
        }

    def _build_delivery(self) -> dict[str, Any]:
        start_id, start = self._node(
            "Start",
            class_name="StartAction",
            position=(80, 120),
            start=True,
            init_patch={"event_types": ["email.sent", "email.delivered"]},
        )
        copy_id, copy_node = self._node(
            "Copy data",
            position=(420, 120),
            init_patch={
                "traits": {
                    "set": {
                        "profile@traits.email_valid": "event@properties.email_valid",
                        "profile@traits.last_email_delivery_status": "event@properties.delivery_status",
                        "profile@traits.last_email_sent_at": "event@properties.timestamp",
                    }
                }
            },
        )
        update_id, update = self._node("Update profile", position=(760, 120))
        return {
            "nodes": [start, copy_node, update],
            "edges": [
                _edge(start_id, "payload", copy_id, "payload"),
                _edge(copy_id, "payload", update_id, "payload"),
            ],
        }

    def _build_engagement(self) -> dict[str, Any]:
        start_id, start = self._node(
            "Start",
            class_name="StartAction",
            position=(80, 120),
            start=True,
            init_patch={"event_types": ["email.opened", "email.clicked"]},
        )
        increment_id, increment = self._node(
            "Increment counter",
            position=(420, 120),
            init_patch={
                "field": "profile@traits.engagement_score",
                "increment": 1,
            },
        )
        copy_id, copy_node = self._node(
            "Copy data",
            position=(760, 120),
            init_patch={
                "traits": {
                    "set": {
                        "profile@traits.last_email_id": "event@properties.email_id",
                        "profile@traits.last_email_engagement_at": "event@properties.timestamp",
                    }
                }
            },
        )
        update_id, update = self._node("Update profile", position=(1100, 120))
        return {
            "nodes": [start, increment, copy_node, update],
            "edges": [
                _edge(start_id, "payload", increment_id, "payload"),
                _edge(increment_id, "payload", copy_id, "payload"),
                _edge(copy_id, "payload", update_id, "payload"),
            ],
        }

    def _build_high_engagement(self) -> dict[str, Any]:
        start_id, start = self._node(
            "Start",
            class_name="StartAction",
            position=(80, 120),
            start=True,
            init_patch={"event_types": ["email.opened", "email.clicked"]},
        )
        if_id, if_node = self._node(
            "If",
            position=(420, 120),
            init_patch={
                "condition": "{{profile@traits.engagement_score >= 5}}",
                "pass_payload": True,
                "trigger_once": False,
                "ttl": 0,
            },
        )
        segment_id, segment = self._node(
            "Add segment",
            position=(760, 40),
            init_patch={"segment": "High Engagement"},
        )
        return {
            "nodes": [start, if_node, segment],
            "edges": [
                _edge(start_id, "payload", if_id, "payload"),
                _edge(if_id, "true", segment_id, "payload"),
            ],
        }


def _make_empty_draft(name: str, description: str) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "description": description,
        "flowGraph": {"nodes": [], "edges": []},
        "response": {},
        "tags": ["General"],
        "lock": False,
        "type": "collection",
        "timestamp": _now_iso(),
        "deploy_timestamp": None,
        "file_name": None,
        "wf_schema": {
            "version": "1.0.x",
            "uri": "http://www.tracardi.com/2021/WFSchema",
            "server_version": "1.0.x",
        },
    }


async def setup_workflows() -> int:
    print("=" * 70)
    print("🚀 Tracardi Workflow Repair")
    print("=" * 70)
    print(f"\nTracardi API: {TRACARDI_API_URL}")
    print(f"Username: {TRACARDI_USERNAME}")

    client = TracardiWorkflowClient(TRACARDI_API_URL, TRACARDI_USERNAME, TRACARDI_PASSWORD)
    print("\n🔐 Authenticating...")
    await client.authenticate()
    print("✅ Authentication successful")

    print("\n📦 Loading plugin catalog...")
    plugins = await client.get_plugin_catalog()
    builder = WorkflowBuilder(plugins)
    print(f"✅ Loaded {len(plugins)} workflow plugins")

    existing_workflows = {flow["name"]: flow for flow in await client.get_workflows()}
    print(f"\n📊 Existing workflows discovered: {len(existing_workflows)}")

    repaired = 0
    created = 0

    for name, spec in WORKFLOW_SPECS.items():
        description = spec["description"]
        if name in existing_workflows:
            draft = await client.get_draft(existing_workflows[name]["id"])
            if draft is None:
                draft = _make_empty_draft(name, description)
            status = "repairing"
            repaired += 1
        else:
            draft = _make_empty_draft(name, description)
            status = "creating"
            created += 1

        draft["name"] = name
        draft["description"] = description
        draft["timestamp"] = draft.get("timestamp") or _now_iso()
        draft["flowGraph"] = builder.build(name)

        print(f"\n  {status.title()}: {name}")
        print(f"    Nodes: {len(draft['flowGraph']['nodes'])}")
        print(f"    Edges: {len(draft['flowGraph']['edges'])}")
        await client.upsert_draft(draft)
        print("    ✅ Draft upserted")

    print("\n" + "=" * 70)
    print("📊 Workflow Repair Summary")
    print("=" * 70)
    print(f"  Repaired existing drafts: {repaired}")
    print(f"  Created missing drafts:   {created}")
    print(f"  Target workflows:         {len(WORKFLOW_SPECS)}")
    print("\nNext steps:")
    print("  1. Open the local Tracardi GUI and confirm the repaired flow layouts")
    print("  2. Send a test email event and verify the profile traits update")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(setup_workflows()))
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        raise SystemExit(1)
