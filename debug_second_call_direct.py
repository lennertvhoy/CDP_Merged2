#!/usr/bin/env python3
"""
Direct test of second call with proper message sequence.

This bypasses LangGraph streaming to isolate the exact failure point.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from src.core.runtime_env import bootstrap_runtime_environment
bootstrap_runtime_environment()

from src.graph.nodes import agent_node, tools_node
from src.graph.state import AgentState


async def test_direct_second_call():
    """Test agent_node directly with second-call message sequence."""
    print("="*70)
    print("DIRECT SECOND CALL TEST (bypassing LangGraph streaming)")
    print("="*70)
    
    # First call - should trigger tool selection
    print("\n[1] First agent_node call (tool selection)...")
    state1: AgentState = {
        "messages": [HumanMessage(content="how many companies in Brussels")],
        "language": "",
        "profile_id": None,
    }
    
    try:
        result1 = await asyncio.wait_for(agent_node(state1), timeout=30)
        print(f"    ✓ First call returned: {type(result1)}")
        
        ai_message = result1["messages"][0]
        print(f"    AI message type: {type(ai_message).__name__}")
        print(f"    Has tool_calls: {hasattr(ai_message, 'tool_calls') and bool(ai_message.tool_calls)}")
        
        if hasattr(ai_message, 'tool_calls') and ai_message.tool_calls:
            print(f"    Tool calls: {[tc.get('name') for tc in ai_message.tool_calls]}")
    except asyncio.TimeoutError:
        print("    ❌ First call TIMED OUT")
        return False
    except Exception as e:
        print(f"    ❌ First call ERROR: {e}")
        return False
    
    # Tools node - execute the tool
    print("\n[2] Tools node execution...")
    state2: AgentState = {
        "messages": state1["messages"] + result1["messages"],
        "language": "en",
        "profile_id": None,
    }
    
    try:
        result2 = await asyncio.wait_for(tools_node(state2, config={"configurable": {"thread_id": "test"}}), timeout=30)
        print(f"    ✓ Tools node returned: {type(result2)}")
        
        if "messages" in result2:
            tool_message = result2["messages"][0]
            print(f"    Tool message type: {type(tool_message).__name__}")
            print(f"    Tool result preview: {str(tool_message.content)[:100]}...")
    except asyncio.TimeoutError:
        print("    ❌ Tools node TIMED OUT")
        return False
    except Exception as e:
        print(f"    ❌ Tools node ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Second agent call - the hanging point
    print("\n[3] Second agent_node call (with ToolMessage) - THE HANG POINT...")
    
    # Build the full message sequence
    messages_after_tool = state2["messages"].copy()
    if "messages" in result2:
        messages_after_tool.extend(result2["messages"])
    
    print(f"    Message sequence:")
    for i, m in enumerate(messages_after_tool):
        print(f"      [{i}] {type(m).__name__}: {str(m)[:60]}...")
    
    state3: AgentState = {
        "messages": messages_after_tool,
        "language": "en",
        "profile_id": None,
    }
    
    try:
        print(f"    Calling agent_node with {len(messages_after_tool)} messages...")
        start = time.monotonic()
        result3 = await asyncio.wait_for(agent_node(state3), timeout=60)
        elapsed = time.monotonic() - start
        print(f"    ✓ Second call returned in {elapsed:.2f}s: {type(result3)}")
        
        final_message = result3["messages"][0]
        print(f"    Final message type: {type(final_message).__name__}")
        print(f"    Content: {getattr(final_message, 'content', 'N/A')[:200]}...")
        return True
        
    except asyncio.TimeoutError:
        print(f"    ❌ Second call TIMED OUT after 60s - HANG CONFIRMED!")
        return False
    except Exception as e:
        print(f"    ❌ Second call ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print(f"Started: {datetime.now().isoformat()}\n")
    
    success = await test_direct_second_call()
    
    print("\n" + "="*70)
    print("RESULT")
    print("="*70)
    if success:
        print("✅ Second call works in direct test!")
        print("The issue is likely in LangGraph streaming/orchestration.")
    else:
        print("❌ Second call hangs even in direct test!")
        print("The issue is in agent_node or Azure OpenAI handling.")


if __name__ == "__main__":
    asyncio.run(main())
