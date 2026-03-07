#!/usr/bin/env python3
"""
deduplicate.py - Merge duplicate Tracardi profiles by KBO number
Identifies profiles with the same KBO and merges them intelligently.
"""
import requests
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deduplication.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ProfileDeduplicator:
    """Deduplicate profiles by KBO number"""
    
    def __init__(self, es_host: str, tracardi_url: str, token: str, dry_run: bool = True):
        self.es_host = es_host
        self.tracardi_url = tracardi_url
        self.token = token
        self.dry_run = dry_run
        self.stats = {
            "duplicate_groups_found": 0,
            "profiles_merged": 0,
            "profiles_deleted": 0,
            "errors": 0,
            "merged_fields": defaultdict(int)
        }
    
    def get_auth_headers(self) -> Dict:
        return {"Authorization": f"Bearer {self.token}"}
    
    def find_duplicate_groups(self, min_size: int = 2) -> Dict[str, List[Dict]]:
        """Find all KBOs with multiple profiles"""
        logger.info("Scanning for duplicate KBO numbers...")
        
        query = {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"exists": {"field": "data.identifier.id"}}
                    ]
                }
            },
            "aggs": {
                "duplicate_kbos": {
                    "terms": {
                        "field": "data.identifier.id",
                        "min_doc_count": min_size,
                        "size": 10000
                    },
                    "aggs": {
                        "profiles": {
                            "top_hits": {
                                "size": 10,
                                "_source": True,
                                "sort": [{"metadata.time.visit": {"order": "desc"}}]
                            }
                        }
                    }
                }
            }
        }
        
        try:
            resp = requests.post(
                f"{self.es_host}/_search",
                json=query,
                timeout=60
            )
            resp.raise_for_status()
            
            data = resp.json()
            buckets = data["aggregations"]["duplicate_kbos"]["buckets"]
            
            groups = {}
            for bucket in buckets:
                kbo = bucket["key"]
                profiles = [hit["_source"] for hit in bucket["profiles"]["hits"]["hits"]]
                groups[kbo] = profiles
            
            self.stats["duplicate_groups_found"] = len(groups)
            logger.info(f"Found {len(groups)} KBOs with duplicates")
            
            return groups
            
        except Exception as e:
            logger.error(f"Error finding duplicates: {e}")
            return {}
    
    def completeness_score(self, profile: Dict) -> int:
        """Calculate data completeness score for ranking"""
        score = 0
        data = profile.get("data", {})
        
        # Contact info (10 points each)
        contact = data.get("contact", {})
        if contact.get("email", {}).get("main"):
            score += 10
        if contact.get("email", {}).get("business"):
            score += 10
        if contact.get("phone", {}).get("main"):
            score += 10
        if contact.get("phone", {}).get("business"):
            score += 10
        
        # Address (15 points)
        address = contact.get("address", {})
        if address.get("street"):
            score += 5
        if address.get("postcode"):
            score += 5
        if address.get("town"):
            score += 5
        
        # Company info (5 points)
        company = data.get("job", {}).get("company", {})
        if company.get("name"):
            score += 5
        if company.get("size"):
            score += 3
        
        # Activity (1 point per visit, max 50)
        visits = profile.get("stats", {}).get("visits", 0)
        score += min(visits, 50)
        
        # Prefer more recent activity
        last_visit = data.get("devices", {}).get("last", {}).get("visit", {}).get("date")
        if last_visit:
            score += 10
        
        return score
    
    def select_primary(self, profiles: List[Dict]) -> Dict:
        """Select the best profile to keep as primary"""
        scored = [(self.completeness_score(p), p) for p in profiles]
        scored.sort(reverse=True)
        return scored[0][1]
    
    def merge_data(self, primary: Dict, secondary: Dict) -> Dict:
        """Merge data from secondary into primary"""
        merged = json.loads(json.dumps(primary))  # Deep copy
        
        # Helper to safely get nested values
        def get_nested(obj, *keys, default=None):
            for key in keys:
                if not isinstance(obj, dict):
                    return default
                obj = obj.get(key, default)
            return obj
        
        # Helper to set nested values
        def set_nested(obj, value, *keys):
            for key in keys[:-1]:
                if key not in obj:
                    obj[key] = {}
                obj = obj[key]
            obj[keys[-1]] = value
        
        # Merge contact info
        for field in ["main", "business"]:
            email = get_nested(secondary, "data", "contact", "email", field)
            if email and not get_nested(merged, "data", "contact", "email", field):
                set_nested(merged, email, "data", "contact", "email", field)
                self.stats["merged_fields"][f"email_{field}"] += 1
        
        for field in ["main", "business", "mobile", "whatsapp"]:
            phone = get_nested(secondary, "data", "contact", "phone", field)
            if phone and not get_nested(merged, "data", "contact", "phone", field):
                set_nested(merged, phone, "data", "contact", "phone", field)
                self.stats["merged_fields"][f"phone_{field}"] += 1
        
        # Merge address
        for field in ["street", "town", "postcode", "county", "country", "other"]:
            addr = get_nested(secondary, "data", "contact", "address", field)
            if addr and not get_nested(merged, "data", "contact", "address", field):
                set_nested(merged, addr, "data", "contact", "address", field)
                self.stats["merged_fields"][f"address_{field}"] += 1
        
        # Merge company info
        for field in ["name", "size", "segment", "country"]:
            company = get_nested(secondary, "data", "job", "company", field)
            if company and not get_nested(merged, "data", "job", "company", field):
                set_nested(merged, company, "data", "job", "company", field)
                self.stats["merged_fields"][f"company_{field}"] += 1
        
        # Aggregate stats
        sec_stats = secondary.get("stats", {})
        merged_stats = merged.get("stats", {})
        for key in ["views", "visits"]:
            merged_stats[key] = merged_stats.get(key, 0) + sec_stats.get(key, 0)
        
        # Merge counters if present
        sec_counters = sec_stats.get("counters", {})
        merged_counters = merged_stats.get("counters", {})
        for key, value in sec_counters.items():
            merged_counters[key] = merged_counters.get(key, 0) + value
        
        # Merge IDs list
        merged_ids = set(merged.get("ids", []))
        merged_ids.add(secondary.get("id"))
        merged_ids.update(secondary.get("ids", []))
        merged["ids"] = list(merged_ids)
        
        # Merge traits
        sec_traits = secondary.get("traits", {})
        merged_traits = merged.get("traits", {})
        for key, value in sec_traits.items():
            if key not in merged_traits:
                merged_traits[key] = value
        
        # Merge segments
        sec_segments = set(secondary.get("segments", []))
        merged_segments = set(merged.get("segments", []))
        merged["segments"] = list(merged_segments | sec_segments)
        
        # Mark as merged
        if "_merge_history" not in merged_traits:
            merged_traits["_merge_history"] = []
        merged_traits["_merge_history"].append({
            "merged_profile_id": secondary.get("id"),
            "merged_at": datetime.now().isoformat(),
            "kbo": get_nested(secondary, "data", "identifier", "id")
        })
        
        merged["traits"] = merged_traits
        
        return merged
    
    def merge_duplicate_group(self, kbo: str, profiles: List[Dict]) -> Optional[Dict]:
        """Merge profiles with the same KBO"""
        if len(profiles) < 2:
            return None
        
        logger.info(f"Processing KBO {kbo} with {len(profiles)} profiles")
        
        # Select primary
        primary = self.select_primary(profiles)
        primary_id = primary["id"]
        
        logger.info(f"  Selected primary: {primary_id} (score: {self.completeness_score(primary)})")
        
        # Merge others into primary
        merged = primary
        deleted_ids = []
        
        for profile in profiles:
            if profile["id"] == primary_id:
                continue
            
            logger.info(f"  Merging: {profile['id']} (score: {self.completeness_score(profile)})")
            merged = self.merge_data(merged, profile)
            deleted_ids.append(profile["id"])
        
        return {
            "merged_profile": merged,
            "deleted_ids": deleted_ids,
            "kbo": kbo
        }
    
    def update_profile(self, profile: Dict) -> bool:
        """Update profile in Tracardi"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update profile: {profile['id']}")
            return True
        
        try:
            resp = requests.post(
                f"{self.tracardi_url}/profiles/import",
                headers=self.get_auth_headers(),
                json=[profile],
                timeout=30
            )
            
            if resp.status_code == 200:
                return True
            else:
                logger.error(f"Failed to update profile {profile['id']}: {resp.text[:500]}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating profile {profile['id']}: {e}")
            return False
    
    def delete_profile(self, profile_id: str) -> bool:
        """Delete profile from Tracardi"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would delete profile: {profile_id}")
            return True
        
        try:
            resp = requests.delete(
                f"{self.tracardi_url}/profile/{profile_id}",
                headers=self.get_auth_headers(),
                timeout=30
            )
            
            if resp.status_code in [200, 204]:
                return True
            else:
                logger.error(f"Failed to delete profile {profile_id}: {resp.text[:500]}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting profile {profile_id}: {e}")
            return False
    
    def run(self) -> Dict:
        """Main deduplication process"""
        logger.info("=" * 60)
        logger.info("STARTING DEDUPLICATION")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info("=" * 60)
        
        # Find all duplicate groups
        groups = self.find_duplicate_groups()
        
        if not groups:
            logger.info("No duplicates found!")
            return dict(self.stats)
        
        # Process each group
        for kbo, profiles in groups.items():
            try:
                result = self.merge_duplicate_group(kbo, profiles)
                if not result:
                    continue
                
                # Update merged profile
                if self.update_profile(result["merged_profile"]):
                    self.stats["profiles_merged"] += 1
                else:
                    self.stats["errors"] += 1
                    continue
                
                # Delete duplicates
                for deleted_id in result["deleted_ids"]:
                    if self.delete_profile(deleted_id):
                        self.stats["profiles_deleted"] += 1
                    else:
                        self.stats["errors"] += 1
                
            except Exception as e:
                logger.error(f"Error processing KBO {kbo}: {e}")
                self.stats["errors"] += 1
        
        logger.info("=" * 60)
        logger.info("DEDUPLICATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Groups processed: {self.stats['duplicate_groups_found']}")
        logger.info(f"Profiles merged: {self.stats['profiles_merged']}")
        logger.info(f"Profiles deleted: {self.stats['profiles_deleted']}")
        logger.info(f"Errors: {self.stats['errors']}")
        logger.info(f"Fields merged: {dict(self.stats['merged_fields'])}")
        
        return dict(self.stats)


def preview_duplicates(es_host: str):
    """Preview duplicate groups without making changes"""
    deduper = ProfileDeduplicator(es_host, "", "", dry_run=True)
    groups = deduper.find_duplicate_groups()
    
    print("\nDuplicate Groups Preview:")
    print("-" * 60)
    
    for kbo, profiles in list(groups.items())[:10]:  # Show first 10
        print(f"\nKBO: {kbo}")
        print(f"  Profiles: {len(profiles)}")
        for p in profiles:
            score = deduper.completeness_score(p)
            email = p.get("data", {}).get("contact", {}).get("email", {}).get("main", "N/A")
            company = p.get("data", {}).get("job", {}).get("company", {}).get("name", "N/A")
            print(f"    - {p['id'][:20]}... (score: {score}, email: {email}, company: {company})")


if __name__ == "__main__":
    import os
    import sys
    
    # Configuration from environment variables
    ES_HOST = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    TRACARDI_URL = os.environ["TRACARDI_API_URL"]  # No default - must be set
    TOKEN = os.environ["TRACARDI_TOKEN"]  # No default - must be set via env var
    
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        preview_duplicates(ES_HOST)
    elif len(sys.argv) > 1 and sys.argv[1] == "--live":
        deduper = ProfileDeduplicator(ES_HOST, TRACARDI_URL, TOKEN, dry_run=False)
        results = deduper.run()
        
        with open(f"dedup_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
            json.dump(results, f, indent=2)
    else:
        print("Usage:")
        print("  python deduplicate.py --preview  # Preview duplicates (dry run)")
        print("  python deduplicate.py --live     # Execute deduplication")
        print("\nDefault mode is DRY RUN for safety.")
        
        # Run in dry-run mode by default
        deduper = ProfileDeduplicator(ES_HOST, TRACARDI_URL, TOKEN, dry_run=True)
        results = deduper.run()
