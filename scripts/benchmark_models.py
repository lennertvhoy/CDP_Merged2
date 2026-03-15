#!/usr/bin/env python3
"""
Model Benchmark Suite for CDP_Merged Operator Shell.
Tests all Azure OpenAI deployments against real workloads.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env.local")

# Configuration
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://aoai-cdpmerged-fast.openai.azure.com/")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-03-01-preview")

# Models to benchmark
MODELS = [
    "gpt-5",
    "gpt-5-mini", 
    "gpt-5-nano",
    "gpt-4o",
    "gpt-4-1",
    "gpt-4-1-mini",
]

# Test scenarios
SCENARIOS = [
    {
        "name": "simple_non_tool",
        "description": "Simple non-tool response",
        "messages": [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Say hello in one sentence.")
        ],
        "bind_tools": False,
        "timeout": 30,
    },
    {
        "name": "simple_count_tool",
        "description": "Simple count with tool use",
        "messages": [
            SystemMessage(content="""You are a helpful assistant for Belgian Enterprise data.

Available tools:
- search_profiles: Search for companies by location, industry, etc.

Use tools when needed to answer questions."""),
            HumanMessage(content="How many companies are in Brussels?")
        ],
        "bind_tools": True,
        "tools": [{
            "type": "function",
            "function": {
                "name": "search_profiles",
                "description": "Search for company profiles",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City or region"},
                        "industry": {"type": "string", "description": "Industry sector"},
                    }
                }
            }
        }],
        "timeout": 60,
    },
    {
        "name": "large_result_search",
        "description": "Large-result search with tool use",
        "messages": [
            SystemMessage(content="""You are a helpful assistant for Belgian Enterprise data.

Available tools:
- search_profiles: Search for companies by location, industry, etc.

Use tools when needed to answer questions."""),
            HumanMessage(content="Find software companies in Antwerp.")
        ],
        "bind_tools": True,
        "tools": [{
            "type": "function",
            "function": {
                "name": "search_profiles",
                "description": "Search for company profiles",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "industry": {"type": "string"},
                    }
                }
            }
        }],
        "timeout": 60,
    },
    {
        "name": "complex_reasoning",
        "description": "Complex multi-step reasoning",
        "messages": [
            SystemMessage(content="You are a helpful assistant for Belgian Enterprise data."),
            HumanMessage(content="""Compare the IT services sector in Brussels vs Antwerp:
1. Which city has more IT companies?
2. What is the approximate employee count difference?
3. Which city has higher total revenue in this sector?

Provide a structured analysis.""")
        ],
        "bind_tools": False,
        "timeout": 45,
    },
]


class BenchmarkResult:
    def __init__(self, model: str, scenario: str):
        self.model = model
        self.scenario = scenario
        self.start_time = None
        self.first_token_time = None
        self.end_time = None
        self.error = None
        self.content = None
        self.tool_calls = None
        self.timing_breakdown = {}
        
    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "scenario": self.scenario,
            "start_time": self.start_time,
            "first_token_time": self.first_token_time,
            "end_time": self.end_time,
            "total_duration_ms": (self.end_time - self.start_time) * 1000 if self.end_time and self.start_time else None,
            "time_to_first_token_ms": (self.first_token_time - self.start_time) * 1000 if self.first_token_time and self.start_time else None,
            "error": self.error,
            "content_preview": self.content[:200] if self.content else None,
            "content_length": len(self.content) if self.content else 0,
            "tool_calls": self.tool_calls,
            "timing_breakdown": self.timing_breakdown,
        }


async def run_benchmark(model_name: str, scenario: dict) -> BenchmarkResult:
    """Run a single benchmark scenario against a model."""
    result = BenchmarkResult(model_name, scenario["name"])
    
    try:
        # Initialize model
        kwargs = {
            "azure_deployment": model_name,
            "azure_endpoint": AZURE_ENDPOINT,
            "api_version": AZURE_API_VERSION,
            "temperature": 0.0,
        }
        
        # Add API key if available
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        if api_key:
            from pydantic import SecretStr
            kwargs["api_key"] = SecretStr(api_key)
        else:
            # Try Azure AD auth
            try:
                from azure.identity import DefaultAzureCredential, get_bearer_token_provider
                credential = DefaultAzureCredential()
                token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
                kwargs["azure_ad_token_provider"] = token_provider
            except Exception as e:
                result.error = f"Auth error: {e}"
                return result
        
        model = AzureChatOpenAI(**kwargs)
        
        # Bind tools if needed
        if scenario.get("bind_tools") and scenario.get("tools"):
            model = model.bind_tools(scenario["tools"])
        
        # Run the benchmark
        result.start_time = time.time()
        
        # Stream to capture first token time
        content_parts = []
        first_token_received = False
        
        async for chunk in model.astream(scenario["messages"]):
            if not first_token_received:
                result.first_token_time = time.time()
                first_token_received = True
            
            if hasattr(chunk, 'content') and chunk.content:
                content_parts.append(chunk.content)
            
            # Check for tool calls
            if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                result.tool_calls = chunk.tool_calls
        
        result.end_time = time.time()
        result.content = "".join(content_parts)
        
        # If no streaming content but we have tool calls, that's still valid
        if not result.content and result.tool_calls:
            result.content = f"[TOOL_CALL: {result.tool_calls}]"
            
    except asyncio.TimeoutError:
        result.error = "TIMEOUT"
        result.end_time = time.time()
    except Exception as e:
        result.error = str(e)
        result.end_time = time.time()
    
    return result


async def benchmark_model(model_name: str) -> list[BenchmarkResult]:
    """Run all scenarios for a single model."""
    print(f"\n{'='*60}")
    print(f"Benchmarking: {model_name}")
    print(f"{'='*60}")
    
    results = []
    for scenario in SCENARIOS:
        print(f"  Testing: {scenario['name']}... ", end="", flush=True)
        
        try:
            result = await asyncio.wait_for(
                run_benchmark(model_name, scenario),
                timeout=scenario.get("timeout", 60)
            )
            results.append(result)
            
            if result.error:
                print(f"FAILED - {result.error[:50]}")
            else:
                duration = (result.end_time - result.start_time) * 1000
                ttft = (result.first_token_time - result.start_time) * 1000 if result.first_token_time else 0
                print(f"OK - {duration:.0f}ms (TTFT: {ttft:.0f}ms)")
                
        except asyncio.TimeoutError:
            result = BenchmarkResult(model_name, scenario["name"])
            result.error = "TIMEOUT"
            results.append(result)
            print("TIMEOUT")
    
    return results


async def main():
    """Run complete benchmark suite."""
    print("="*60)
    print("CDP_Merged Model Benchmark Suite")
    print(f"Started: {datetime.now().isoformat()}")
    print(f"Endpoint: {AZURE_ENDPOINT}")
    print("="*60)
    
    all_results = []
    
    for model in MODELS:
        try:
            results = await benchmark_model(model)
            all_results.extend(results)
        except Exception as e:
            print(f"ERROR benchmarking {model}: {e}")
    
    # Generate report
    print("\n" + "="*60)
    print("BENCHMARK RESULTS SUMMARY")
    print("="*60)
    
    # Group by model
    by_model = {}
    for r in all_results:
        if r.model not in by_model:
            by_model[r.model] = []
        by_model[r.model].append(r)
    
    for model, results in sorted(by_model.items()):
        print(f"\n{model}:")
        for r in results:
            if r.error:
                print(f"  {r.scenario:25} FAIL - {r.error[:40]}")
            else:
                duration = (r.end_time - r.start_time) * 1000
                print(f"  {r.scenario:25} OK   - {duration:6.0f}ms")
    
    # Save detailed results
    output = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": AZURE_ENDPOINT,
        "results": [r.to_dict() for r in all_results],
    }
    
    output_file = Path(__file__).parent.parent / "output" / "model_benchmark_results.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: {output_file}")
    
    return all_results


if __name__ == "__main__":
    asyncio.run(main())
