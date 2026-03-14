#!/usr/bin/env python3
"""Direct response quality test using the LangGraph workflow directly.

Bypasses HTTP auth/cookies and tests the actual response generation
to verify the source-level system prompt fix.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.runtime_env import bootstrap_runtime_environment
bootstrap_runtime_environment()

from langchain_core.messages import HumanMessage, SystemMessage
from src.graph.nodes import agent_node, router_node, tools_node, _build_system_prompt
from src.graph.state import AgentState


TEST_PROMPTS = [
    {
        "id": "market_research_count",
        "category": "market_research",
        "prompt": "How many IT companies are in Brussels?",
        "expects": ["number", "companies", "Brussels"],
        "forbids": ["1.", "2.", "I need to", "I will use", "search_profiles"],
    },
    {
        "id": "360_profile",
        "category": "account_360",
        "prompt": "Show me a 360 view of B.B.S. Entreprise",
        "expects": ["B.B.S.", "company", "profile"],
        "forbids": ["1.", "2.", "I need to", "query_unified"],
    },
    {
        "id": "segmentation",
        "category": "segmentation",
        "prompt": "Create a segment of dentists in Antwerp",
        "expects": ["segment", "dentists", "Antwerp"],
        "forbids": ["1.", "2.", "I will use create_segment"],
    },
    {
        "id": "operational_count",
        "category": "operational",
        "prompt": "How many companies have websites?",
        "expects": ["companies", "websites"],
        "forbids": ["1.", "2.", "I need to"],
    },
    {
        "id": "follow_up",
        "category": "follow_up",
        "prompt": "Add email filter to that search",
        "context": "Previous: searched for IT companies in Brussels",
        "expects": ["email", "filter"],
        "forbids": ["1.", "2.", "I will use"],
    },
    {
        "id": "awkward_phrasing",
        "category": "edge_case",
        "prompt": "um... so like find me some companies or whatever?",
        "expects": [],  # Just check it doesn't crash
        "forbids": ["1.", "2.", "3."],
    },
]


def check_response_quality(response_text: str, test_case: dict) -> dict:
    """Check response against quality criteria."""
    response_lower = response_text.lower()
    
    results = {
        "answer_first": True,
        "no_numbered_steps": True,
        "no_tool_leakage": True,
        "no_thinking_preamble": True,
        "has_expected_content": True,
        "score": 10.0,
    }
    
    # Check for forbidden patterns
    for forbidden in test_case.get("forbids", []):
        if forbidden.lower() in response_lower:
            if forbidden in ["1.", "2.", "3."]:
                results["no_numbered_steps"] = False
                results["score"] -= 2.0
            elif "I need to" in forbidden or "I will use" in forbidden:
                results["no_thinking_preamble"] = False
                results["score"] -= 2.0
            elif "search_profiles" in forbidden or "query_unified" in forbidden or "create_segment" in forbidden:
                results["no_tool_leakage"] = False
                results["score"] -= 3.0
    
    # Check for expected content
    for expected in test_case.get("expects", []):
        if expected.lower() not in response_lower:
            results["has_expected_content"] = False
            results["score"] -= 1.0
    
    # Check answer-first (no preamble before the actual answer)
    first_line = response_text.strip().split('\n')[0] if response_text.strip() else ""
    preamble_indicators = ["i need", "i will", "let me", "first", "step", "searching"]
    if any(p in first_line.lower() for p in preamble_indicators):
        results["answer_first"] = False
        results["score"] -= 2.0
    
    results["score"] = max(0, results["score"])
    results["passed"] = results["score"] >= 7.0
    
    return results


async def test_workflow_response(prompt: str, system_prompt: str | None = None) -> str:
    """Get response from workflow for a single prompt."""
    messages = []
    
    # Add system prompt
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    else:
        messages.append(SystemMessage(content=_build_system_prompt("en")))
    
    # Add user message
    messages.append(HumanMessage(content=prompt))
    
    # Create state
    state = AgentState(messages=messages, language="en")
    
    # Run router node
    router_result = await router_node(state)
    if router_result.get("messages"):
        messages.extend(router_result["messages"])
    
    # Run agent node
    agent_result = await agent_node(state)
    agent_response = agent_result["messages"][0]
    
    return agent_response.content


async def main():
    print("="*60)
    print("Response Quality Direct Test")
    print("="*60)
    print()
    
    # Get current system prompt
    system_prompt = _build_system_prompt("en")
    print("System prompt preview (first 500 chars):")
    print(system_prompt[:500])
    print("...")
    print()
    
    # Check if the fix is in place
    if "answer the user's question FIRST" in system_prompt:
        print("✅ Source-level fix detected: 'answer the user's question FIRST'")
    else:
        print("⚠️ Source-level fix NOT detected")
    print()
    
    # Run tests
    results = []
    for test in TEST_PROMPTS:
        print(f"Testing: {test['id']} ({test['category']})")
        print(f"  Prompt: {test['prompt'][:60]}...")
        
        try:
            start = time.time()
            response = await asyncio.wait_for(
                test_workflow_response(test['prompt'], system_prompt),
                timeout=30
            )
            duration = time.time() - start
            
            # Truncate for display
            response_preview = response[:200].replace('\n', ' ') + "..." if len(response) > 200 else response
            print(f"  Response: {response_preview}")
            
            # Check quality
            quality = check_response_quality(response, test)
            print(f"  Quality Score: {quality['score']}/10")
            print(f"  Checks: answer_first={quality['answer_first']}, no_steps={quality['no_numbered_steps']}, no_leakage={quality['no_tool_leakage']}")
            print(f"  Duration: {duration:.2f}s")
            print(f"  Status: {'✅ PASS' if quality['passed'] else '❌ FAIL'}")
            
            results.append({
                "id": test['id'],
                "category": test['category'],
                "score": quality['score'],
                "passed": quality['passed'],
                "duration": duration,
                "response_preview": response_preview,
            })
            
        except asyncio.TimeoutError:
            print(f"  ❌ TIMEOUT (>30s)")
            results.append({
                "id": test['id'],
                "category": test['category'],
                "score": 0,
                "passed": False,
                "error": "timeout",
            })
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            results.append({
                "id": test['id'],
                "category": test['category'],
                "score": 0,
                "passed": False,
                "error": str(e),
            })
        print()
    
    # Summary
    print("="*60)
    print("SUMMARY")
    print("="*60)
    passed = sum(1 for r in results if r.get('passed'))
    total = len(results)
    avg_score = sum(r.get('score', 0) for r in results) / total if total else 0
    
    print(f"Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Pass Rate: {passed/total*100:.1f}%")
    print(f"Avg Score: {avg_score:.1f}/10")
    
    # Save results
    output_dir = Path("reports/evals")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "response_quality_direct.json"
    
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "test_type": "direct_workflow",
            "total_tests": total,
            "passed": passed,
            "avg_score": avg_score,
            "results": results,
        }, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
