#!/usr/bin/env python3
"""
Debug the EXACT production path using astream_events with full message history.

This tests whether the issue is in LangGraph's astream_events handling
when the workflow includes tool calls and ToolMessages.
"""

import asyncio
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from langchain_core.messages import HumanMessage

from src.core.runtime_env import bootstrap_runtime_environment
bootstrap_runtime_environment()

from src.graph.workflow import compile_workflow


async def test_astream_events_with_history():
    """Test astream_events with full conversation history including ToolMessage."""
    print("="*70)
    print("ASTREAM_EVENTS TEST (EXACT PRODUCTION PATH)")
    print("="*70)
    
    # Compile workflow exactly like production
    workflow = compile_workflow(checkpointer=None)
    
    # Test 1: Simple query (baseline)
    print("\n[TEST 1] Simple query (no tools)...")
    thread_id_1 = f"test-simple-{int(time.time())}"
    inputs_1 = {
        "messages": [HumanMessage(content="say hi")],
        "language": "",
        "profile_id": None,
    }
    config_1 = {"configurable": {"thread_id": thread_id_1}}
    
    chunks_1 = []
    event_count_1 = 0
    start_1 = time.monotonic()
    
    try:
        async with asyncio.timeout(30):
            async for event in workflow.astream_events(inputs_1, config=config_1, version="v2"):
                event_count_1 += 1
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", {})
                    if hasattr(chunk, "content") and chunk.content:
                        chunks_1.append(chunk.content)
        
        elapsed_1 = time.monotonic() - start_1
        print(f"    ✅ SUCCESS: {event_count_1} events, {elapsed_1:.2f}s")
        print(f"    Content: '{''.join(chunks_1)[:50]}...'")
        
    except asyncio.TimeoutError:
        print(f"    ❌ TIMEOUT")
        return False
    
    # Wait a bit for rate limit
    print("\n    [Waiting 5s for rate limit...]")
    await asyncio.sleep(5)
    
    # Test 2: Tool query (the problematic case)
    print("\n[TEST 2] Tool query (how many companies)...")
    thread_id_2 = f"test-tool-{int(time.time())}"
    inputs_2 = {
        "messages": [HumanMessage(content="how many companies in Brussels")],
        "language": "",
        "profile_id": None,
    }
    config_2 = {"configurable": {"thread_id": thread_id_2}}
    
    event_count_2 = 0
    agent_calls = 0
    tool_calls = 0
    chunks_2 = []
    stages = []
    
    start_2 = time.monotonic()
    last_event_time = start_2
    
    try:
        async with asyncio.timeout(90):
            async for event in workflow.astream_events(inputs_2, config=config_2, version="v2"):
                now = time.monotonic()
                elapsed_since_last = now - last_event_time
                last_event_time = now
                
                event_count_2 += 1
                kind = event.get("event", "")
                name = event.get("name", "")
                
                # Track key stages
                if kind == "on_chain_start" and name == "agent":
                    agent_calls += 1
                    stages.append(f"agent_{agent_calls}_start")
                    print(f"\n    [{event_count_2}] Agent call #{agent_calls} started")
                    
                elif kind == "on_chain_end" and name == "agent":
                    stages.append(f"agent_{agent_calls}_end")
                    print(f"    [{event_count_2}] Agent call #{agent_calls} ended")
                    
                elif kind == "on_tool_start":
                    tool_calls += 1
                    stages.append(f"tool_{name}_start")
                    print(f"    [{event_count_2}] Tool started: {name}")
                    
                elif kind == "on_tool_end":
                    stages.append(f"tool_{name}_end")
                    print(f"    [{event_count_2}] Tool ended: {name}")
                    
                elif kind == "on_chat_model_start":
                    stages.append(f"llm_start")
                    print(f"    [{event_count_2}] LLM call starting...")
                    
                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", {})
                    if hasattr(chunk, "content") and chunk.content:
                        chunks_2.append(chunk.content)
                        
                # Detect stalls
                if elapsed_since_last > 5:
                    print(f"    ⚠️  STALL: {elapsed_since_last:.1f}s since last event")
                    
        elapsed_2 = time.monotonic() - start_2
        print(f"\n    ✅ SUCCESS: {event_count_2} events, {elapsed_2:.2f}s")
        print(f"    Agent calls: {agent_calls}, Tool calls: {tool_calls}")
        print(f"    Content: '{''.join(chunks_2)[:100]}...'")
        return True
        
    except asyncio.TimeoutError:
        elapsed_2 = time.monotonic() - start_2
        print(f"\n    ❌ TIMEOUT after {elapsed_2:.1f}s")
        print(f"    Events: {event_count_2}, Agent calls: {agent_calls}, Tool calls: {tool_calls}")
        print(f"    Stages reached: {stages}")
        return False


async def main():
    print(f"Started: {datetime.now().isoformat()}\n")
    
    success = await test_astream_events_with_history()
    
    print("\n" + "="*70)
    print("CONCLUSION")
    print("="*70)
    if success:
        print("✅ astream_events works with tool workflows!")
        print("The issue may be elsewhere in production (checkpointer, etc).")
    else:
        print("❌ astream_events hangs with tool workflows!")
        print("This confirms the issue is in LangGraph streaming.")


if __name__ == "__main__":
    asyncio.run(main())
