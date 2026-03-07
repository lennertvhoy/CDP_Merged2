#!/usr/bin/env python3
"""
Memory Backend Performance Comparison
Tests: Cloud Mem0, Local Mem0 (if available), File-based MEMORY.md
"""

import time
import requests
import json
import statistics

# Test configurations
CLOUD_API_KEY = "m0-xCRL8v9fiMlboRDTIUPkMdn71fWmlo3kTBbrFf1E"
CLOUD_ENDPOINT = "https://api.mem0.ai/v1"
LOCAL_ENDPOINT = "http://localhost:8000/v1"  # If running local Mem0

def benchmark_cloud_store(text, runs=5):
    """Benchmark cloud Mem0 store latency"""
    times = []
    for i in range(runs):
        start = time.time()
        response = requests.post(
            f"{CLOUD_ENDPOINT}/memories/",
            headers={"Authorization": f"Token {CLOUD_API_KEY}"},
            json={
                "messages": [{"role": "user", "content": f"Test memory {i}: {text}"}],
                "user_id": "benchmark"
            }
        )
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times),
        "std": statistics.stdev(times) if len(times) > 1 else 0
    }

def benchmark_cloud_search(query, runs=5):
    """Benchmark cloud Mem0 search latency"""
    times = []
    for i in range(runs):
        start = time.time()
        response = requests.get(
            f"{CLOUD_ENDPOINT}/memories/?user_id=benchmark",
            headers={"Authorization": f"Token {CLOUD_API_KEY}"}
        )
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times)
    }

def benchmark_file_read(runs=5):
    """Benchmark file-based MEMORY.md read"""
    times = []
    memory_path = '/home/ff/.openclaw/workspace/MEMORY.md'
    for i in range(runs):
        start = time.time()
        with open(memory_path, 'r') as f:
            content = f.read()
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times)
    }

def benchmark_file_write(runs=5):
    """Benchmark file-based write latency"""
    times = []
    test_path = '/home/ff/.openclaw/workspace/CDP_Merged/reports/test_write.md'
    for i in range(runs):
        start = time.time()
        with open(test_path, 'w') as f:
            f.write(f"Test memory {i}: Benchmarking write performance\n")
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)
    # Cleanup
    import os
    if os.path.exists(test_path):
        os.remove(test_path)
    return {
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "min": min(times),
        "max": max(times)
    }

def run_full_benchmark():
    """Run complete benchmark suite"""
    print("=== Memory Backend Performance Comparison ===\n")
    
    # Cloud Mem0
    print("Testing Cloud Mem0 (app.mem0.ai)...")
    store_results = benchmark_cloud_store("Test memory for benchmarking", runs=5)
    search_results = benchmark_cloud_search("test query", runs=5)
    
    print(f"\n📊 Cloud Mem0 Results:")
    print(f"  Store Latency: {store_results['mean']:.1f}ms avg (min: {store_results['min']:.1f}ms, max: {store_results['max']:.1f}ms)")
    print(f"  Search Latency: {search_results['mean']:.1f}ms avg (min: {search_results['min']:.1f}ms, max: {search_results['max']:.1f}ms)")
    
    # File-based
    print("\nTesting File-based (MEMORY.md)...")
    file_read_results = benchmark_file_read(runs=5)
    file_write_results = benchmark_file_write(runs=5)
    
    print(f"\n📊 File-based Results:")
    print(f"  Read Latency: {file_read_results['mean']:.1f}ms avg (min: {file_read_results['min']:.1f}ms, max: {file_read_results['max']:.1f}ms)")
    print(f"  Write Latency: {file_write_results['mean']:.1f}ms avg (min: {file_write_results['min']:.1f}ms, max: {file_write_results['max']:.1f}ms)")
    
    # Comparison
    print("\n=== Summary ===")
    print(f"Cloud Mem0 Store: {store_results['mean']:.1f}ms")
    print(f"Cloud Mem0 Search: {search_results['mean']:.1f}ms")
    print(f"File Read: {file_read_results['mean']:.1f}ms")
    print(f"File Write: {file_write_results['mean']:.1f}ms")
    print(f"\nCloud Store is {store_results['mean']/file_write_results['mean']:.1f}x slower than file write")
    print(f"Cloud Search is {search_results['mean']/file_read_results['mean']:.1f}x slower than file read")
    
    return {
        "cloud_store": store_results,
        "cloud_search": search_results,
        "file_read": file_read_results,
        "file_write": file_write_results
    }

if __name__ == "__main__":
    results = run_full_benchmark()
    
    # Save results
    with open('/home/ff/.openclaw/workspace/CDP_Merged/reports/memory_benchmark.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\n✅ Results saved to reports/memory_benchmark.json")
