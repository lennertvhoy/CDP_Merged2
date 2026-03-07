#!/usr/bin/env python3
"""
profile_analyzer_api.py - Analyze Tracardi profile data quality via API
Uses Tracardi REST API instead of direct Elasticsearch access.
"""
import requests
import json
import sys
from collections import defaultdict
from datetime import datetime

class ProfileAnalyzerAPI:
    def __init__(self, tracardi_url, token):
        self.tracardi_url = tracardi_url
        self.token = token
        self.stats = defaultdict(lambda: {"exists": 0, "missing": 0, "samples": []})
        self.sample_profiles = []
    
    def get_auth_headers(self):
        return {"Authorization": f"Bearer {self.token}"}
    
    def get_profile_count(self):
        """Get total profile count"""
        try:
            resp = requests.get(
                f"{self.tracardi_url}/profile/count",
                headers=self.get_auth_headers(),
                timeout=30
            )
            resp.raise_for_status()
            return resp.json().get("count", 0)
        except Exception as e:
            print(f"Error getting count: {e}")
            return 0
    
    def fetch_sample_profiles(self, limit=100):
        """Fetch sample profiles for analysis"""
        try:
            resp = requests.get(
                f"{self.tracardi_url}/profiles/top/modified?limit={limit}",
                headers=self.get_auth_headers(),
                timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", [])
        except Exception as e:
            print(f"Error fetching profiles: {e}")
            return []
    
    def analyze_field(self, profiles, field_path, getter_func):
        """Analyze a specific field across profiles"""
        populated = 0
        for p in profiles:
            if getter_func(p):
                populated += 1
        return populated
    
    def find_kbo_duplicates(self, profiles):
        """Find profiles with duplicate KBO numbers"""
        kbo_map = defaultdict(list)
        
        for p in profiles:
            # Check traits.enterprise_number
            kbo = p.get("traits", {}).get("enterprise_number")
            if kbo:
                kbo_map[kbo].append(p.get("id"))
            # Check data.identifier.id
            identifier = p.get("data", {}).get("identifier", {}).get("id")
            if identifier:
                kbo_map[identifier].append(p.get("id"))
        
        # Find duplicates
        duplicates = {kbo: ids for kbo, ids in kbo_map.items() if len(ids) >= 2}
        return duplicates
    
    def validate_email(self, email):
        """Simple email validation"""
        if not email:
            return False
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, str(email).lower().strip()))
    
    def validate_phone(self, phone):
        """Simple phone validation"""
        if not phone:
            return False
        digits = ''.join(c for c in str(phone) if c.isdigit())
        return len(digits) >= 8
    
    def validate_postcode(self, postcode):
        """Validate Belgian postcode"""
        if not postcode:
            return False
        try:
            code = int(''.join(c for c in str(postcode) if c.isdigit()))
            return 1000 <= code <= 9999
        except:
            return False
    
    def analyze_data_quality(self):
        """Run full data quality analysis"""
        print("=" * 70)
        print("TRACARDI PROFILE DATA QUALITY ANALYSIS (via API)")
        print("=" * 70)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"Tracardi URL: {self.tracardi_url}")
        print()
        
        # Total count
        total = self.get_profile_count()
        print(f"Total Profiles: {total:,}")
        print()
        
        # Fetch sample for analysis
        print("Fetching sample profiles for analysis...")
        sample_size = min(1000, total)
        profiles = self.fetch_sample_profiles(sample_size)
        
        if not profiles:
            print("ERROR: Could not fetch profiles for analysis")
            return None
        
        print(f"Analyzing {len(profiles)} profiles...")
        print()
        
        # Field analysis
        print("-" * 70)
        print("FIELD POPULATION ANALYSIS (Sample)")
        print("-" * 70)
        print(f"{'Field':<30} {'Populated':>12} {'Missing':>12} {'%':>8}")
        print("-" * 70)
        
        fields = [
            ("Enterprise Number (traits)", lambda p: p.get("traits", {}).get("enterprise_number")),
            ("KBO (data.identifier.id)", lambda p: p.get("data", {}).get("identifier", {}).get("id")),
            ("Email (main)", lambda p: p.get("data", {}).get("contact", {}).get("email", {}).get("main")),
            ("Email (business)", lambda p: p.get("data", {}).get("contact", {}).get("email", {}).get("business")),
            ("Email (traits)", lambda p: p.get("traits", {}).get("email")),
            ("Phone (main)", lambda p: p.get("data", {}).get("contact", {}).get("phone", {}).get("main")),
            ("Phone (business)", lambda p: p.get("data", {}).get("contact", {}).get("phone", {}).get("business")),
            ("Phone (traits)", lambda p: p.get("traits", {}).get("phone")),
            ("Address Street", lambda p: p.get("data", {}).get("contact", {}).get("address", {}).get("street")),
            ("Address Postcode", lambda p: p.get("data", {}).get("contact", {}).get("address", {}).get("postcode")),
            ("Address Town", lambda p: p.get("data", {}).get("contact", {}).get("address", {}).get("town")),
            ("City (traits)", lambda p: p.get("traits", {}).get("city")),
            ("Company Name (traits)", lambda p: p.get("traits", {}).get("name")),
        ]
        
        field_stats = {}
        for label, getter in fields:
            populated = self.analyze_field(profiles, label, getter)
            missing = len(profiles) - populated
            pct = (populated / len(profiles) * 100) if profiles else 0
            field_stats[label] = {"populated": populated, "missing": missing, "pct": pct}
            print(f"{label:<30} {populated:>12,} {missing:>12,} {pct:>7.1f}%")
        
        print()
        
        # Duplicate analysis (on sample)
        print("-" * 70)
        print("DUPLICATE ANALYSIS (Sample)")
        print("-" * 70)
        
        duplicates = self.find_kbo_duplicates(profiles)
        duplicate_count = len(duplicates)
        total_dup_profiles = sum(len(ids) for ids in duplicates.values())
        
        print(f"KBO numbers with duplicates in sample: {duplicate_count}")
        print(f"Total duplicate profiles in sample: {total_dup_profiles}")
        
        if duplicates:
            print("\nTop duplicated KBOs:")
            for kbo, ids in list(duplicates.items())[:10]:
                print(f"  KBO {kbo}: {len(ids)} profiles")
        
        # Estimate total duplicates
        if duplicate_count > 0 and len(profiles) > 0:
            estimated_total_dups = int((total_dup_profiles / len(profiles)) * total)
            print(f"\nEstimated total duplicates (projection): {estimated_total_dups:,}")
        
        print()
        
        # Data quality issues
        print("-" * 70)
        print("DATA QUALITY ISSUES (Sample)")
        print("-" * 70)
        
        invalid_emails = 0
        invalid_phones = 0
        invalid_postcodes = 0
        
        for p in profiles:
            email = p.get("data", {}).get("contact", {}).get("email", {}).get("main") or \
                    p.get("traits", {}).get("email")
            if email and not self.validate_email(email):
                invalid_emails += 1
            
            phone = p.get("data", {}).get("contact", {}).get("phone", {}).get("main") or \
                    p.get("traits", {}).get("phone")
            if phone and not self.validate_phone(phone):
                invalid_phones += 1
            
            postcode = p.get("data", {}).get("contact", {}).get("address", {}).get("postcode") or \
                       p.get("traits", {}).get("zipcode")
            if postcode and not self.validate_postcode(postcode):
                invalid_postcodes += 1
        
        print(f"Invalid email formats: {invalid_emails}")
        print(f"Invalid phone formats: {invalid_phones}")
        print(f"Invalid postcodes: {invalid_postcodes}")
        
        print()
        
        # Sample profiles
        print("-" * 70)
        print("SAMPLE PROFILES")
        print("-" * 70)
        
        for i, p in enumerate(profiles[:3], 1):
            print(f"\n--- Sample {i} ---")
            print(f"ID: {p.get('id')}")
            
            traits = p.get("traits", {})
            data = p.get("data", {})
            contact = data.get("contact", {})
            email = contact.get("email", {})
            phone = contact.get("phone", {})
            address = contact.get("address", {})
            
            print(f"Enterprise/KBO: {traits.get('enterprise_number') or data.get('identifier', {}).get('id', 'N/A')}")
            print(f"Name: {traits.get('name', 'N/A')}")
            print(f"Email: {email.get('main') or email.get('business') or traits.get('email', 'N/A')}")
            print(f"Phone: {phone.get('main') or phone.get('business') or traits.get('phone', 'N/A')}")
            print(f"Address: {address.get('street') or traits.get('street', 'N/A')}, {address.get('postcode') or traits.get('zipcode', 'N/A')} {address.get('town') or traits.get('city', 'N/A')}")
            print(f"Active: {p.get('active', 'N/A')}")
        
        print()
        print("=" * 70)
        print("ANALYSIS COMPLETE")
        print("=" * 70)
        
        return {
            "total": total,
            "sample_size": len(profiles),
            "field_stats": field_stats,
            "duplicates_sample": {"duplicate_kbos": duplicate_count, "total_dup_profiles": total_dup_profiles},
            "quality_issues": {"invalid_emails": invalid_emails, "invalid_phones": invalid_phones, "invalid_postcodes": invalid_postcodes}
        }


if __name__ == "__main__":
    # Configuration from environment or defaults
    import os
    TRACARDI_URL = os.environ["TRACARDI_API_URL"]  # No default - must be set
    TOKEN = os.environ["TRACARDI_TOKEN"]  # No default - must be set via env var
    
    print("Profile Analyzer (API Mode)")
    print("============================")
    print(f"Tracardi URL: {TRACARDI_URL}")
    print()
    
    try:
        analyzer = ProfileAnalyzerAPI(TRACARDI_URL, TOKEN)
        results = analyzer.analyze_data_quality()
        
        if results:
            # Save results
            output_file = f"data_quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nDetailed report saved to: {output_file}")
        else:
            sys.exit(1)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
