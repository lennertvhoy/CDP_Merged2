#!/usr/bin/env python3
"""
Debug script for second-call hang with full LangGraph instrumentation.

This script reproduces the EXACT production flow including:
- LangGraph workflow compilation
- astream_events streaming
- Tool execution
- Second agent call with ToolMessage
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from langchain_core.messages import HumanMessage

# Bootstrap runtime environment FIRST
from src.core.runtime_env import bootstrap_runtime_environment
bootstrap_runtime_environment()

from src.graph.workflow import compile_workflow
from src.config import settings

# Enable detailed logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_TIMEOUT = 60  # seconds per stage


async def test_full_workflow_with_tools():
    """
    Test full LangGraph workflow with tool execution.
    
    Flow:
    1. HumanMessage -> agent_node (selects tool)
    2. critic_node (validates tool)
    3. tools_node (executes tool)
    4. agent_node (second call with ToolMessage) <- HANGS HERE
    """
    print("\n" + "="*70)
    print("FULL LANGGRAPH WORKFLOW TEST WITH TOOL EXECUTION")
    print("="*70)
    print(f"Started: {datetime.now().isoformat()}")
    print(f"LLM Provider: {settings.LLM_PROVIDER}")
    print(f"Azure Deployment: {settings.AZURE_OPENAI_DEPLOYMENT_NAME}")
    print("-"*70)
    
    # Compile workflow exactly like production
    print("\n[1/5] Compiling workflow...")
    workflow_start = time.monotonic()
    workflow = compile_workflow(checkpointer=None)  # Same as production now
    print(f"    ✓ Workflow compiled in {time.monotonic() - workflow_start:.2f}s")
    
    # Setup exactly like production
    thread_id = f"debug-{int(time.time())}"
    inputs = {
        "messages": [HumanMessage(content="how many companies in Brussels")],
        "language": "",
        "profile_id": None,
    }
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"\n[2/5] Initial state prepared:")
    print(f"    Thread ID: {thread_id}")
    print(f"    Input message: 'how many companies in Brussels'")
    print(f"    Config: {config}")
    
    # Track events
    event_count = 0
    tool_calls_seen = []
    agent_calls = 0
    
    print(f"\n[3/5] Starting astream_events (timeout={TEST_TIMEOUT}s)...")
    print("-"*70)
    
    stream_start = time.monotonic()
    
    try:
        async with asyncio.timeout(TEST_TIMEOUT):
            async for event in workflow.astream_events(inputs, config=config, version="v2"):
                event_count += 1
                kind = event.get("event", "")
                name = event.get("name", "")
                
                # Log key events
                if kind == "on_chain_start":
                    print(f"\n[{event_count}] on_chain_start: {name}")
                    if name == "agent":
                        agent_calls += 1
                        print(f"    >>> AGENT_NODE CALL #{agent_calls} STARTING <<<")
                        
                elif kind == "on_chain_end":
                    print(f"[{event_count}] on_chain_end: {name}")
                    
                elif kind == "on_chat_model_start":
                    print(f"[{event_count}] on_chat_model_start: {name}")
                    
                elif kind == "on_chat_model_stream":
                    # Only log first stream chunk to avoid spam
                    if event_count <= 50:  # Log first 50 events
                        chunk = event.get("data", {}).get("chunk", {})
                        if hasattr(chunk, "content"):
                            print(f"[{event_count}] on_chat_model_stream: content='{chunk.content[:50]}...'")
                            
                elif kind == "on_chat_model_end":
                    print(f"[{event_count}] on_chat_model_end: {name}")
                    
                elif kind == "on_tool_start":
                    print(f"[{event_count}] on_tool_start: {name}")
                    tool_calls_seen.append(name)
                    
                elif kind == "on_tool_end":
                    print(f"[{event_count}] on_tool_end: {name}")
                    
                # Track ALL events for first 20, then sample
                if event_count <= 20:
                    print(f"    Event data keys: {list(event.keys())}")
                    
        stream_duration = time.monotonic() - stream_start
        print("-"*70)
        print(f"\n[4/5] Stream completed!")
        print(f"    Total events: {event_count}")
        print(f"    Stream duration: {stream_duration:.2f}s")
        print(f"    Agent calls: {agent_calls}")
        print(f"    Tool calls: {tool_calls_seen}")
        
        if agent_calls >= 2:
            print(f"\n    ✅ SUCCESS: Second agent call completed!")
            return True
        else:
            print(f"\n    ⚠️  WARNING: Only {agent_calls} agent call(s) seen (expected 2)")
            return False
            
    except asyncio.TimeoutError:
        print(f"\n[4/5] ❌ TIMEOUT after {TEST_TIMEOUT}s - HANG DETECTED!")
        print(f"    Events processed: {event_count}")
        print(f"    Agent calls: {agent_calls}")
        print(f"    Tool calls: {tool_calls_seen}")
        print(f"    Last event kind: {kind if 'kind' in locals() else 'N/A'}")
        print(f"    Last event name: {name if 'name' in locals() else 'N/A'}")
        return False
        
    except Exception as e:
        print(f"\n[4/5] ❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_simple_workflow_no_tools():
    """Test simple workflow without tools (baseline)."""
    print("\n" + "="*70)
    print("BASELINE: SIMPLE WORKFLOW WITHOUT TOOLS")
    print("="*70)
    
    workflow = compile_workflow(checkpointer=None)
    thread_id = f"debug-simple-{int(time.time())}"
    inputs = {
        "messages": [HumanMessage(content="say hi briefly")],
        "language": "",
        "profile_id": None,
    }
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"Input: 'say hi briefly'")
    
    event_count = 0
    start = time.monotonic()
    
    try:
        async with asyncio.timeout(TEST_TIMEOUT):
            async for event in workflow.astream_events(inputs, config=config, version="v2"):
                event_count += 1
                kind = event.get("event", "")
                if kind in ("on_chat_model_stream",):
                    chunk = event.get("data", {}).get("chunk", {})
                    if hasattr(chunk, "content") and chunk.content:
                        print(f"  Chunk: {chunk.content}", end="")
                        
        elapsed = time.monotonic() - start
        print(f"\n\n✅ SUCCESS: {event_count} events, {elapsed:.2f}s")
        return True
        
    except asyncio.TimeoutError:
        print(f"\n\n❌ TIMEOUT - Hang detected!")
        return False
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        return False


async def main():
    print("="*70)
    print("LANGGRAPH SECOND-CALL HANG DIAGNOSTIC")
    print(f"Started: {datetime.now().isoformat()}")
    print("="*70)
    
    # Test 1: Simple workflow (should work)
    simple_ok = await test_simple_workflow_no_tools()
    
    # Test 2: Full workflow with tools (may hang)
    if simple_ok:
        tool_ok = await test_full_workflow_with_tools()
    else:
        print("\nSkipping tool test - simple workflow failed")
        tool_ok = False
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Simple workflow (no tools): {'✅ PASS' if simple_ok else '❌ FAIL'}")
    print(f"Tool workflow (2nd call):   {'✅ PASS' if tool_ok else '❌ FAIL'}")
    
    if not tool_ok and simple_ok:
        print("\n🔍 DIAGNOSIS: Hang occurs specifically with tool-using workflows")
        print("   The issue is likely in the LangGraph tool-handling path.")
    elif not simple_ok:
        print("\n🔍 DIAGNOSIS: Even simple workflow hangs - broader issue")
    else:
        print("\n✅ Both tests passed - hang may be specific to production conditions")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(0 if exit_code else 1)
