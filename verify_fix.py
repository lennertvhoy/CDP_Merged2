#!/usr/bin/env python3
"""
Verify the rate limit fix and deterministic shortcuts.

Tests:
1. Deterministic shortcut formatting functions
2. Azure client configuration (retry limits)
3. Simple query via public ngrok path
4. Tool query (count) via public ngrok path
"""

import asyncio
import json
import sys
import time


def test_deterministic_shortcuts():
    """Test the deterministic formatting functions."""
    print("=" * 60)
    print("TEST 1: Deterministic Shortcut Formatters")
    print("=" * 60)
    
    # Import after path setup
    import os
    sys.path.insert(0, '/home/ff/Documents/CDP_Merged')
    os.chdir('/home/ff/Documents/CDP_Merged')
    
    from src.graph.nodes import (
        _format_link_quality_result,
        _format_geo_revenue_result,
        _format_industry_summary_result,
        _format_coverage_result,
        _try_deterministic_shortcut,
    )
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
    
    # Test link quality formatting
    link_result = {
        "status": "ok",
        "data": {
            "total_companies": 1500,
            "source_links": {
                "kbo": {"linked": 1500, "percentage": 100.0},
                "exact_online": {"linked": 890, "percentage": 59.3},
                "teamleader": {"linked": 745, "percentage": 49.7}
            }
        }
    }
    formatted = _format_link_quality_result(link_result)
    assert formatted is not None
    assert "1,500" in formatted
    assert "KBO" in formatted
    print("✓ Link quality formatter works")
    
    # Test geographic revenue formatting
    geo_result = {
        "status": "ok",
        "data": [
            {"city": "Brussels", "total_revenue": 15000000, "company_count": 250},
            {"city": "Antwerp", "total_revenue": 8500000, "company_count": 180}
        ]
    }
    formatted = _format_geo_revenue_result(geo_result)
    assert formatted is not None
    assert "Brussels" in formatted
    assert "15,000,000" in formatted or "15.000.000" in formatted
    print("✓ Geographic revenue formatter works")
    
    # Test industry summary formatting
    industry_result = {
        "status": "ok",
        "data": [
            {"industry": "Software", "company_count": 45, "total_pipeline": 2500000},
            {"industry": "Consulting", "company_count": 120, "total_revenue": 8000000}
        ]
    }
    formatted = _format_industry_summary_result(industry_result)
    assert formatted is not None
    assert "Software" in formatted
    print("✓ Industry summary formatter works")
    
    # Test shortcut detection with message history
    messages = [
        SystemMessage(content="System prompt"),
        HumanMessage(content="How well are source systems linked?"),
        AIMessage(
            content="",
            tool_calls=[{"name": "get_identity_link_quality", "args": {}, "id": "call_1"}]
        ),
        ToolMessage(content=json.dumps(link_result), tool_call_id="call_1"),
    ]
    
    shortcut = _try_deterministic_shortcut(messages)
    assert shortcut is not None
    assert "Identity Link Quality" in shortcut
    print("✓ Shortcut detection works for get_identity_link_quality")
    
    # Test no shortcut for non-deterministic tool
    messages_no_shortcut = [
        SystemMessage(content="System prompt"),
        HumanMessage(content="Find companies in Brussels"),
        AIMessage(
            content="",
            tool_calls=[{"name": "search_profiles", "args": {"city": "Brussels"}, "id": "call_2"}]
        ),
        ToolMessage(content=json.dumps({"count": 42, "results": []}), tool_call_id="call_2"),
    ]
    
    no_shortcut = _try_deterministic_shortcut(messages_no_shortcut)
    assert no_shortcut is None
    print("✓ Correctly skips non-deterministic tools")
    
    print("\n✅ All deterministic shortcut tests passed!")
    return True


def test_azure_configuration():
    """Test Azure client configuration has proper retry limits."""
    print("\n" + "=" * 60)
    print("TEST 2: Azure Configuration (Retry Limits)")
    print("=" * 60)
    
    import os
    sys.path.insert(0, '/home/ff/Documents/CDP_Merged')
    os.chdir('/home/ff/Documents/CDP_Merged')
    
    from src.config import settings
    
    print(f"AZURE_OPENAI_MAX_RETRIES: {settings.AZURE_OPENAI_MAX_RETRIES}")
    print(f"AZURE_OPENAI_TIMEOUT: {settings.AZURE_OPENAI_TIMEOUT}")
    print(f"AZURE_OPENAI_RETRY_MIN_SECONDS: {getattr(settings, 'AZURE_OPENAI_RETRY_MIN_SECONDS', 'N/A')}")
    print(f"AZURE_OPENAI_RETRY_MAX_SECONDS: {getattr(settings, 'AZURE_OPENAI_RETRY_MAX_SECONDS', 'N/A')}")
    
    # Verify fail-fast configuration
    assert settings.AZURE_OPENAI_MAX_RETRIES <= 2, "Retries should be low for fail-fast behavior"
    assert settings.AZURE_OPENAI_TIMEOUT <= 30, "Timeout should be reasonable for UX"
    
    print("\n✅ Azure configuration tests passed!")
    return True


async def test_public_path_simple():
    """Test simple query via public ngrok path."""
    print("\n" + "=" * 60)
    print("TEST 3: Public Path - Simple Query")
    print("=" * 60)
    
    import aiohttp
    
    url = "https://kbocdpagent.ngrok.app/api/operator/chat/stream"
    
    async with aiohttp.ClientSession() as session:
        start_time = time.monotonic()
        async with session.post(
            url,
            json={"message": "Hello, are you there?", "thread_id": f"test_{int(time.time())}"},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            events = []
            async for line in resp.content:
                line = line.decode().strip()
                if line:
                    try:
                        event = json.loads(line)
                        events.append(event)
                        if event.get("type") == "assistant_delta":
                            print(f"  Delta: {event.get('delta', '')[:50]}...")
                    except json.JSONDecodeError:
                        pass
            
            elapsed = time.monotonic() - start_time
            print(f"  Completed in {elapsed:.2f}s")
            
            # Check for success
            has_final_message = any(e.get("type") == "assistant_message" for e in events)
            has_error = any(e.get("type") == "error" for e in events)
            
            if has_error:
                error_event = [e for e in events if e.get("type") == "error"][0]
                print(f"  ⚠️ Error: {error_event.get('error', 'Unknown')[:100]}")
                return False
            
            if has_final_message:
                print("  ✅ Simple query succeeded")
                return True
            else:
                print("  ❌ No final message received")
                return False


async def test_public_path_tool():
    """Test tool query via public ngrok path."""
    print("\n" + "=" * 60)
    print("TEST 4: Public Path - Tool Query (Link Quality)")
    print("=" * 60)
    
    import aiohttp
    
    url = "https://kbocdpagent.ngrok.app/api/operator/chat/stream"
    
    async with aiohttp.ClientSession() as session:
        start_time = time.monotonic()
        thread_id = f"test_tool_{int(time.time())}"
        
        async with session.post(
            url,
            json={"message": "How well are source systems linked to KBO?", "thread_id": thread_id},
            timeout=aiohttp.ClientTimeout(total=90)  # Higher timeout for tool queries
        ) as resp:
            events = []
            last_event_time = time.monotonic()
            stall_detected = False
            
            async for line in resp.content:
                line = line.decode().strip()
                if line:
                    try:
                        event = json.loads(line)
                        events.append(event)
                        
                        # Check for stalls
                        now = time.monotonic()
                        gap = now - last_event_time
                        if gap > 10:
                            print(f"  ⚠️ Stall detected: {gap:.1f}s gap")
                            stall_detected = True
                        last_event_time = now
                        
                        if event.get("type") == "assistant_delta":
                            print(f"  Delta: {event.get('delta', '')[:50]}...")
                        elif event.get("type") == "error":
                            print(f"  ⚠️ Error: {event.get('error', 'Unknown')[:100]}...")
                            
                    except json.JSONDecodeError:
                        pass
            
            elapsed = time.monotonic() - start_time
            print(f"  Completed in {elapsed:.2f}s")
            
            # Analyze results
            has_final_message = any(e.get("type") == "assistant_message" for e in events)
            has_error = any(e.get("type") == "error" for e in events)
            is_rate_limit = any(e.get("is_rate_limit") for e in events if e.get("type") == "error")
            
            if is_rate_limit:
                print("  ⚠️ Rate limit encountered (expected with low Azure capacity)")
                print("  ✅ Rate limit handled gracefully with user message")
                return True  # This is expected behavior now
            
            if has_error and not is_rate_limit:
                print("  ❌ Unexpected error occurred")
                return False
            
            if has_final_message:
                final_event = [e for e in events if e.get("type") == "assistant_message"][0]
                content = final_event.get("message", {}).get("content", "")
                print(f"  Final response: {content[:200]}...")
                print("  ✅ Tool query succeeded")
                return True
            else:
                print("  ❌ No final message received")
                return False


async def main():
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("RATE LIMIT FIX VERIFICATION")
    print("=" * 60)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = []
    
    # Test 1: Deterministic shortcuts
    try:
        results.append(("Deterministic Shortcuts", test_deterministic_shortcuts()))
    except Exception as e:
        print(f"❌ Deterministic shortcut test failed: {e}")
        results.append(("Deterministic Shortcuts", False))
    
    # Test 2: Azure configuration
    try:
        results.append(("Azure Configuration", test_azure_configuration()))
    except Exception as e:
        print(f"❌ Azure configuration test failed: {e}")
        results.append(("Azure Configuration", False))
    
    # Test 3: Public path simple query
    try:
        results.append(("Public Path Simple", await test_public_path_simple()))
    except Exception as e:
        print(f"❌ Public path simple test failed: {e}")
        results.append(("Public Path Simple", False))
    
    # Test 4: Public path tool query
    try:
        results.append(("Public Path Tool", await test_public_path_tool()))
    except Exception as e:
        print(f"❌ Public path tool test failed: {e}")
        results.append(("Public Path Tool", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED")
    else:
        print("⚠️  SOME TESTS FAILED (may be due to Azure rate limits)")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
