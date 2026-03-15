#!/usr/bin/env python3
"""
Minimal reproducer for second-call hang after tool execution.

Goal: Isolate whether the hang is in:
1. AzureChatOpenAI direct call
2. LangGraph orchestration  
3. Message shaping
4. Streaming wrapper
5. App-specific code

This script tests AzureChatOpenAI directly with synthetic conversation flow
mimicking the exact second-call pattern that hangs in production.
"""

import asyncio
import os
import sys
import json
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool

# Enable detailed logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration matching production
TEST_TIMEOUT = 60  # seconds
AZURE_DEPLOYMENT = "gpt-4o"  # Same as production


def get_azure_model():
    """Get AzureChatOpenAI model matching production config."""
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    
    model = AzureChatOpenAI(
        azure_deployment=AZURE_DEPLOYMENT,
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version="2024-08-01-preview",
        temperature=0.0,
    )
    return model


# Define a simple test tool matching production pattern
@tool
def search_profiles(query: str) -> str:
    """Search for companies matching query criteria."""
    return json.dumps({
        "count": 41290,
        "sample": [{"id": "1", "name": "Test Company"}]
    })


async def test_simple_call():
    """Test 1: Simple non-tool call (baseline - should work)."""
    print("\n" + "="*60)
    print("TEST 1: Simple call without tools (baseline)")
    print("="*60)
    
    model = get_azure_model()
    messages = [HumanMessage(content="Say hi briefly")]
    
    print(f"Messages: {[type(m).__name__ for m in messages]}")
    print(f"Model type: {type(model).__name__}")
    
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            model.ainvoke(messages),
            timeout=TEST_TIMEOUT
        )
        elapsed = time.monotonic() - start
        print(f"✅ SUCCESS: Response in {elapsed:.2f}s")
        print(f"Content: {result.content[:100]}...")
        return True
    except asyncio.TimeoutError:
        print(f"❌ TIMEOUT: No response after {TEST_TIMEOUT}s")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return False


async def test_first_call_with_tools():
    """Test 2: First call with tools bound (should trigger tool call)."""
    print("\n" + "="*60)
    print("TEST 2: First call with tools bound (tool selection)")
    print("="*60)
    
    model = get_azure_model()
    tools = [search_profiles]
    model_with_tools = model.bind_tools(tools)
    
    messages = [HumanMessage(content="Find companies in Brussels")]
    
    print(f"Messages: {[type(m).__name__ for m in messages]}")
    print(f"Model type: {type(model_with_tools).__name__}")
    print(f"Tools bound: {len(tools)}")
    
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            model_with_tools.ainvoke(messages),
            timeout=TEST_TIMEOUT
        )
        elapsed = time.monotonic() - start
        print(f"✅ SUCCESS: Response in {elapsed:.2f}s")
        print(f"Content: {result.content[:200] if result.content else '(empty)'}")
        print(f"Tool calls: {result.tool_calls}")
        return True, result
    except asyncio.TimeoutError:
        print(f"❌ TIMEOUT: No response after {TEST_TIMEOUT}s")
        return False, None
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return False, None


async def test_second_call_with_toolmessage():
    """Test 3: Second call with ToolMessage (the hanging pattern)."""
    print("\n" + "="*60)
    print("TEST 3: Second call with ToolMessage (REPRODUCE HANG)")
    print("="*60)
    
    model = get_azure_model()
    tools = [search_profiles]
    model_with_tools = model.bind_tools(tools)
    
    # Build conversation matching production flow
    messages = [
        HumanMessage(content="Find companies in Brussels"),
        AIMessage(
            content="",
            tool_calls=[{
                "id": "call_123",
                "name": "search_profiles",
                "args": {"query": "Brussels"}
            }]
        ),
        ToolMessage(
            content=json.dumps({
                "count": 41290,
                "results": [{"id": "1", "name": "Test"}]
            }),
            tool_call_id="call_123"
        )
    ]
    
    print(f"Message sequence:")
    for i, m in enumerate(messages):
        print(f"  [{i}] {type(m).__name__}: {str(m)[:80]}...")
    
    print(f"\nModel type: {type(model_with_tools).__name__}")
    print(f"Tools still bound: True")
    
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            model_with_tools.ainvoke(messages),
            timeout=TEST_TIMEOUT
        )
        elapsed = time.monotonic() - start
        print(f"✅ SUCCESS: Response in {elapsed:.2f}s")
        print(f"Content: {result.content[:200]}")
        return True
    except asyncio.TimeoutError:
        print(f"❌ TIMEOUT: No response after {TEST_TIMEOUT}s - HANG REPRODUCED!")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_second_call_no_tools_bound():
    """Test 4: Second call WITHOUT tools bound (variant test)."""
    print("\n" + "="*60)
    print("TEST 4: Second call WITHOUT tools bound (variant)")
    print("="*60)
    
    model = get_azure_model()
    # NO tools bound on second call
    
    messages = [
        HumanMessage(content="Find companies in Brussels"),
        AIMessage(
            content="",
            tool_calls=[{
                "id": "call_456",
                "name": "search_profiles",
                "args": {"query": "Brussels"}
            }]
        ),
        ToolMessage(
            content=json.dumps({"count": 41290}),
            tool_call_id="call_456"
        )
    ]
    
    print(f"Message sequence: {[type(m).__name__ for m in messages]}")
    print(f"Model type: {type(model).__name__}")
    print(f"Tools bound: False")
    
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            model.ainvoke(messages),
            timeout=TEST_TIMEOUT
        )
        elapsed = time.monotonic() - start
        print(f"✅ SUCCESS: Response in {elapsed:.2f}s")
        print(f"Content: {result.content[:200]}")
        return True
    except asyncio.TimeoutError:
        print(f"❌ TIMEOUT: No response after {TEST_TIMEOUT}s")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return False


async def test_second_call_simplified_result():
    """Test 5: Second call with SHORT tool result (bounded result)."""
    print("\n" + "="*60)
    print("TEST 5: Second call with SHORT tool result (bounded)")
    print("="*60)
    
    model = get_azure_model()
    tools = [search_profiles]
    model_with_tools = model.bind_tools(tools)
    
    messages = [
        HumanMessage(content="Find companies in Brussels"),
        AIMessage(
            content="",
            tool_calls=[{
                "id": "call_789",
                "name": "search_profiles",
                "args": {"query": "Brussels"}
            }]
        ),
        ToolMessage(
            content="Found 41290 companies",  # Very short result
            tool_call_id="call_789"
        )
    ]
    
    print(f"Tool result size: {len(messages[-1].content)} chars")
    
    start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            model_with_tools.ainvoke(messages),
            timeout=TEST_TIMEOUT
        )
        elapsed = time.monotonic() - start
        print(f"✅ SUCCESS: Response in {elapsed:.2f}s")
        print(f"Content: {result.content[:200]}")
        return True
    except asyncio.TimeoutError:
        print(f"❌ TIMEOUT: No response after {TEST_TIMEOUT}s")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return False


async def main():
    """Run all test variants."""
    print("="*60)
    print("SECOND-CALL HANG REPRODUCER")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Azure Deployment: {AZURE_DEPLOYMENT}")
    print("="*60)
    
    results = {}
    
    # Test 1: Simple baseline
    results["simple_call"] = await test_simple_call()
    
    # Test 2: First call with tools
    success, ai_response = await test_first_call_with_tools()
    results["first_call_tools"] = success
    
    # Test 3: Second call with ToolMessage (main suspect)
    results["second_call_toolmessage"] = await test_second_call_with_toolmessage()
    
    # Test 4: Second call without tools bound
    results["second_call_no_tools"] = await test_second_call_no_tools_bound()
    
    # Test 5: Second call with short result
    results["second_call_short"] = await test_second_call_simplified_result()
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    failed_tests = [name for name, passed in results.items() if not passed]
    if failed_tests:
        print(f"\nFailed tests: {', '.join(failed_tests)}")
        return 1
    else:
        print("\nAll tests passed!")
        return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
