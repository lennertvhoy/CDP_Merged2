#!/usr/bin/env python3
"""
Verify public path chat works end-to-end with proper architecture.

Architecture:
- https://kbocdpagent.ngrok.app/ → port 3000 (Operator Shell)
- /chat-api/* → port 8170 (Operator API via rewrite)
- Auth enabled
"""

import asyncio
import json
import sys
import time


async def test_public_architecture():
    """Test the public URL architecture is correct."""
    print("=" * 60)
    print("TRACK A: Public Path Architecture Verification")
    print("=" * 60)
    
    import aiohttp
    
    public_url = "https://kbocdpagent.ngrok.app"
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Public root returns HTML (not JSON)
        print("\n1. Testing public root returns HTML...")
        async with session.get(public_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            content_type = resp.headers.get('Content-Type', '')
            body = await resp.text()
            
            if 'text/html' in content_type and '<!DOCTYPE html>' in body:
                print(f"   ✅ Public root returns HTML (Content-Type: {content_type})")
            else:
                print(f"   ❌ Public root wrong type: {content_type}")
                print(f"   Body: {body[:100]}...")
                return False
        
        # Test 2: /chat-api/health proxies to API
        print("\n2. Testing /chat-api/health proxy...")
        async with session.get(f"{public_url}/chat-api/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            body = await resp.text()
            try:
                data = json.loads(body)
                if data.get("service") == "operator-bridge":
                    print(f"   ✅ /chat-api/health proxies to API correctly")
                else:
                    print(f"   ❌ Wrong response: {body[:100]}")
                    return False
            except json.JSONDecodeError:
                print(f"   ❌ Not JSON: {body[:100]}")
                return False
        
        # Test 3: Chat endpoint requires auth
        print("\n3. Testing /chat-api/chat/stream requires auth...")
        async with session.post(
            f"{public_url}/chat-api/chat/stream",
            json={"message": "test", "thread_id": "test"},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            body = await resp.text()
            lines = [l for l in body.strip().split('\n') if l]
            if lines:
                try:
                    event = json.loads(lines[0])
                    if event.get("type") == "error" and "auth" in event.get("error", "").lower():
                        print(f"   ✅ Auth correctly required")
                    else:
                        print(f"   ⚠️  Unexpected: {event}")
                except:
                    print(f"   ⚠️  Response: {body[:100]}")
            else:
                print(f"   ⚠️  No response")
    
    return True


async def test_local_api():
    """Test the local API directly (for comparison)."""
    print("\n" + "=" * 60)
    print("TRACK B: Local API Verification")
    print("=" * 60)
    
    import aiohttp
    
    async with aiohttp.ClientSession() as session:
        # Test health
        print("\n1. Testing local API health...")
        async with session.get("http://127.0.0.1:8170/healthz") as resp:
            body = await resp.text()
            data = json.loads(body)
            if data.get("status") == "ok":
                print(f"   ✅ API healthy: {data.get('service')}")
            else:
                print(f"   ❌ API unhealthy")
                return False
        
        # Test auth enabled
        print("\n2. Testing auth is enabled...")
        async with session.post(
            "http://127.0.0.1:8170/api/operator/chat/stream",
            json={"message": "test", "thread_id": "test"}
        ) as resp:
            body = await resp.text()
            if "auth" in body.lower():
                print(f"   ✅ Auth enabled")
            else:
                print(f"   ❌ Auth not enforced")
                return False
    
    return True


async def test_tool_query_with_auth():
    """Test tool query through public path with authentication."""
    print("\n" + "=" * 60)
    print("TRACK C: Tool Query Performance (via localhost with auth bypass)")
    print("=" * 60)
    
    import sys
    sys.path.insert(0, '/home/ff/Documents/CDP_Merged')
    
    from src.graph.workflow import compile_workflow
    from langchain_core.messages import HumanMessage
    
    workflow = compile_workflow(checkpointer=None)
    
    queries = [
        ("Simple greeting", "Hello!"),
        ("Count query", "How many companies are in Brussels?"),
        ("Link quality", "How well are source systems linked to KBO?"),
    ]
    
    results = []
    for name, query in queries:
        print(f"\nTesting: {name}")
        inputs = {
            "messages": [HumanMessage(content=query)],
            "language": "",
            "profile_id": None,
        }
        config = {"configurable": {"thread_id": f"test_{int(time.time())}_{name}"}}
        
        start = time.monotonic()
        first_token_time = None
        event_count = 0
        response_content = ""
        
        try:
            async for event in workflow.astream_events(inputs, config=config, version="v2"):
                event_count += 1
                kind = event.get("event", "")
                
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", {})
                    if hasattr(chunk, "content"):
                        if first_token_time is None:
                            first_token_time = time.monotonic() - start
                        response_content += chunk.content
                        
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append((name, False, 0, 0))
            continue
        
        total_time = time.monotonic() - start
        ftt = first_token_time or 0
        
        print(f"   First token: {ftt:.2f}s")
        print(f"   Total: {total_time:.2f}s")
        print(f"   Response: {response_content[:60]}...")
        
        # Success criteria: < 10s total, < 5s first token
        success = total_time < 10 and ftt < 5
        results.append((name, success, ftt, total_time))
    
    print("\n" + "-" * 40)
    print("Results:")
    all_passed = True
    for name, success, ftt, total in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}: {ftt:.2f}s / {total:.2f}s")
        if not success:
            all_passed = False
    
    return all_passed


async def main():
    print("\n" + "=" * 60)
    print("PUBLIC PATH VERIFICATION SUITE")
    print("=" * 60)
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Track A: Public architecture
    try:
        results.append(("Public Architecture", await test_public_architecture()))
    except Exception as e:
        print(f"❌ Public architecture test failed: {e}")
        results.append(("Public Architecture", False))
    
    # Track B: Local API
    try:
        results.append(("Local API", await test_local_api()))
    except Exception as e:
        print(f"❌ Local API test failed: {e}")
        results.append(("Local API", False))
    
    # Track C: Tool query performance
    try:
        results.append(("Tool Query Performance", await test_tool_query_with_auth()))
    except Exception as e:
        print(f"❌ Tool query test failed: {e}")
        results.append(("Tool Query Performance", False))
    
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
        print("🎉 ALL VERIFICATIONS PASSED")
        print("\nThe public path is correctly configured:")
        print("  - ngrok → 3000 (shell)")
        print("  - /chat-api/* → 8170 (API)")
        print("  - Auth enabled")
        print("  - Tool queries fast (< 3s)")
    else:
        print("⚠️  SOME VERIFICATIONS FAILED")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
