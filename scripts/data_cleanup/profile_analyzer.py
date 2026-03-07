#!/usr/bin/env python3
"""
profile_analyzer.py - Analyze existing profile data quality
Run this first to understand the current state of your data.
"""
import requests
import json
import sys
from collections import defaultdict
from datetime import datetime

class ProfileAnalyzer:
    def __init__(self, es_host, index_name):
        self.es_host = es_host
        self.index = index_name
        self.stats = defaultdict(lambda: {"exists": 0, "missing": 0, "samples": []})
    
    def count_total(self):
        """Get total document count"""
        resp = requests.get(f"{self.es_host}/{self.index}/_count")
        return resp.json().get("count", 0)
    
    def get_field_stats(self, field_path):
        """Get statistics for a field using aggregations"""
        query = {
            "size": 0,
            "aggs": {
                "with_field": {
                    "filter": {"exists": {"field": field_path}}
                },
                "missing_field": {
                    "missing": {"field": field_path}
                }
            }
        }
        try:
            resp = requests.post(f"{self.es_host}/{self.index}/_search", json=query)
            data = resp.json()
            with_field = data["aggregations"]["with_field"]["doc_count"]
            missing_field = data["aggregations"]["missing_field"]["doc_count"]
            return {"with_field": with_field, "missing": missing_field}
        except Exception as e:
            print(f"Error getting stats for {field_path}: {e}")
            return {"with_field": 0, "missing": 0}
    
    def find_duplicates(self, field, size=1000):
        """Find duplicate values in a field"""
        query = {
            "size": 0,
            "aggs": {
                "duplicates": {
                    "terms": {
                        "field": field,
                        "min_doc_count": 2,
                        "size": size
                    }
                }
            }
        }
        try:
            resp = requests.post(f"{self.es_host}/{self.index}/_search", json=query)
            data = resp.json()
            buckets = data["aggregations"]["duplicates"]["buckets"]
            return {
                "duplicate_values": len(buckets),
                "total_duplicates": sum(b["doc_count"] for b in buckets),
                "top_duplicates": buckets[:10]
            }
        except Exception as e:
            print(f"Error finding duplicates for {field}: {e}")
            return {"duplicate_values": 0, "total_duplicates": 0, "top_duplicates": []}
    
    def sample_profiles(self, n=100):
        """Get sample profiles for inspection"""
        query = {
            "size": n,
            "query": {"match_all": {}},
            "_source": True
        }
        try:
            resp = requests.post(f"{self.es_host}/{self.index}/_search", json=query)
            return resp.json().get("hits", {}).get("hits", [])
        except Exception as e:
            print(f"Error sampling profiles: {e}")
            return []
    
    def analyze_data_quality(self):
        """Run full data quality analysis"""
        print("=" * 60)
        print("TRACARDI PROFILE DATA QUALITY ANALYSIS")
        print("=" * 60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()
        
        # Total count
        total = self.count_total()
        print(f"Total Profiles: {total:,}")
        print()
        
        # Fields to analyze
        fields = [
            ("KBO Number", "data.identifier.id"),
            ("Email (Main)", "data.contact.email.main"),
            ("Email (Business)", "data.contact.email.business"),
            ("Phone (Main)", "data.contact.phone.main"),
            ("Phone (Business)", "data.contact.phone.business"),
            ("Address Street", "data.contact.address.street"),
            ("Address Postcode", "data.contact.address.postcode"),
            ("Address Town", "data.contact.address.town"),
            ("Company Name", "data.job.company.name"),
            ("Company Country", "data.job.company.country"),
        ]
        
        print("-" * 60)
        print("FIELD POPULATION ANALYSIS")
        print("-" * 60)
        print(f"{'Field':<25} {'Populated':>12} {'Missing':>12} {'%':>8}")
        print("-" * 60)
        
        for label, field in fields:
            stats = self.get_field_stats(field)
            populated = stats["with_field"]
            missing = stats["missing"]
            pct = (populated / total * 100) if total > 0 else 0
            print(f"{label:<25} {populated:>12,} {missing:>12,} {pct:>7.1f}%")
        
        print()
        
        # Duplicate analysis
        print("-" * 60)
        print("DUPLICATE ANALYSIS")
        print("-" * 60)
        
        dup_stats = self.find_duplicates("data.identifier.id")
        print(f"KBO numbers with duplicates: {dup_stats['duplicate_values']}")
        print(f"Total duplicate profiles: {dup_stats['total_duplicates']}")
        
        if dup_stats['top_duplicates']:
            print("\nTop 10 most duplicated KBOs:")
            for bucket in dup_stats['top_duplicates']:
                print(f"  KBO {bucket['key']}: {bucket['doc_count']} profiles")
        
        print()
        
        # Sample profiles
        print("-" * 60)
        print("SAMPLE PROFILES")
        print("-" * 60)
        
        samples = self.sample_profiles(3)
        for i, hit in enumerate(samples, 1):
            profile = hit.get("_source", {})
            print(f"\n--- Sample {i} ---")
            print(f"ID: {profile.get('id')}")
            
            data = profile.get("data", {})
            identifier = data.get("identifier", {})
            contact = data.get("contact", {})
            email = contact.get("email", {})
            phone = contact.get("phone", {})
            address = contact.get("address", {})
            job = data.get("job", {})
            company = job.get("company", {})
            
            print(f"KBO: {identifier.get('id', 'N/A')}")
            print(f"Email: {email.get('main') or email.get('business', 'N/A')}")
            print(f"Phone: {phone.get('main') or phone.get('business', 'N/A')}")
            print(f"Address: {address.get('street', 'N/A')}, {address.get('postcode', 'N/A')} {address.get('town', 'N/A')}")
            print(f"Company: {company.get('name', 'N/A')}")
            print(f"Active: {profile.get('active', 'N/A')}")
        
        print()
        print("=" * 60)
        print("ANALYSIS COMPLETE")
        print("=" * 60)
        
        return {
            "total": total,
            "fields": {label: self.get_field_stats(field) for label, field in fields},
            "duplicates": dup_stats
        }

if __name__ == "__main__":
    # Configuration
    ES_HOST = "http://localhost:9200"  # Change to ES host
    INDEX_NAME = "09x.8504a.tracardi-profile-2026-q1"  # Update with actual index
    
    print("Profile Analyzer")
    print("================")
    print(f"ES Host: {ES_HOST}")
    print(f"Index: {INDEX_NAME}")
    print()
    
    try:
        analyzer = ProfileAnalyzer(ES_HOST, INDEX_NAME)
        results = analyzer.analyze_data_quality()
        
        # Save results
        output_file = f"data_quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed report saved to: {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
