#!/usr/bin/env python3
"""
bulk_cleanup.py - Full production cleanup for Tracardi profiles
Processes profiles in batches, validates data, and updates via Tracardi API.
"""
import requests
import json
import re
import logging
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cleanup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Validation regex patterns
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
BE_POSTCODE_RANGE = set(range(1000, 10000))
COMPANY_SUFFIXES = [
    'bv', 'b.v', 'b.v.', 'bvba', 'b.v.b.a', 'b.v.b.a.',
    'nv', 'n.v', 'n.v.', 'vzw', 'v.z.w', 'v.z.w.',
    'cv', 'c.v', 'c.v.', 'cvba', 'c.v.b.a', 'c.v.b.a.',
    'comm.v', 'comm. v', 'ec', 'gmbh', 'ltd', 'llc'
]


class DataValidator:
    """Validation and normalization functions"""
    
    @staticmethod
    def validate_email(email: Optional[str]) -> Tuple[Optional[str], str]:
        """Validate and normalize email address"""
        if not email:
            return None, "empty"
        
        email = email.lower().strip()
        
        if not EMAIL_REGEX.match(email):
            return None, "invalid_format"
        
        return email, "valid"
    
    @staticmethod
    def normalize_belgian_phone(phone: Optional[str]) -> Optional[str]:
        """Normalize to +32 XXX XX XX XX format"""
        if not phone:
            return None
        
        digits = re.sub(r'\D', '', phone)
        
        if digits.startswith('32'):
            digits = digits[2:]
        elif digits.startswith('0'):
            digits = digits[1:]
        elif digits.startswith('+') and len(digits) > 2:
            digits = digits[3:] if digits[1:3] == '32' else digits[1:]
        
        if len(digits) < 8 or len(digits) > 10:
            return None
        
        return f"+32 {digits[:3]} {digits[3:5]} {digits[5:7]} {digits[7:]}"
    
    @staticmethod
    def validate_postcode(postcode) -> Optional[str]:
        """Validate Belgian postcode (1000-9999)"""
        if not postcode:
            return None
        
        digits = re.sub(r'\D', '', str(postcode))
        
        try:
            code = int(digits)
            if code in BE_POSTCODE_RANGE:
                return str(code)
        except ValueError:
            pass
        
        return None
    
    @staticmethod
    def validate_kbo(kbo) -> Optional[str]:
        """Validate Belgian KBO/BCE number (10 digits with checksum)"""
        if not kbo:
            return None
        
        digits = re.sub(r'\D', '', str(kbo))
        
        if len(digits) != 10:
            return None
        
        try:
            number = int(digits[:9])
            checksum = int(digits[9])
            calculated = number % 97
            if calculated == checksum or (calculated == 0 and checksum == 97):
                return digits
        except ValueError:
            pass
        
        return None
    
    @staticmethod
    def standardize_company_name(name: Optional[str]) -> Optional[str]:
        """Standardize company name"""
        if not name:
            return None
        
        name = ' '.join(name.split())
        words = name.lower().split()
        standardized = []
        
        for word in words:
            if word.upper() in ['SA', 'SAS', 'SC', 'SCRL', 'SPRL']:
                standardized.append(word.upper())
            else:
                standardized.append(word.capitalize())
        
        name = ' '.join(standardized)
        
        for suffix in COMPANY_SUFFIXES:
            pattern = rf'\b{suffix}\b\.?$'
            if re.search(pattern, name, re.IGNORECASE):
                name = re.sub(pattern, 'BV', name, flags=re.IGNORECASE)
                break
        
        return name
    
    @staticmethod
    def format_nace(nace) -> Optional[str]:
        """Normalize NACE code to XXXXXX format"""
        if not nace:
            return None
        
        digits = re.sub(r'\D', '', str(nace))
        
        if len(digits) < 4 or len(digits) > 6:
            return None
        
        return digits.zfill(6)


class ProfileCleaner:
    """Main cleanup orchestrator"""
    
    def __init__(self, es_host: str, tracardi_url: str, token: str, batch_size: int = 100):
        self.es_host = es_host
        self.tracardi_url = tracardi_url
        self.token = token
        self.batch_size = batch_size
        self.validator = DataValidator()
        self.stats = {
            "processed": 0,
            "updated": 0,
            "errors": 0,
            "validation_failures": defaultdict(int),
            "start_time": None,
            "end_time": None
        }
    
    def get_auth_headers(self) -> Dict:
        return {"Authorization": f"Bearer {self.token}"}
    
    def fetch_batch(self, offset: int) -> List[Dict]:
        """Fetch batch of profiles from Elasticsearch"""
        query = {
            "size": self.batch_size,
            "from": offset,
            "query": {"match_all": {}},
            "_source": True
        }
        
        try:
            resp = requests.post(
                f"{self.es_host}/_search",
                json=query,
                timeout=30
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", {}).get("hits", [])
            return [hit.get("_source", {}) for hit in hits]
        except Exception as e:
            logger.error(f"Error fetching batch at offset {offset}: {e}")
            return []
    
    def clean_profile(self, profile: Dict) -> Optional[Dict]:
        """Apply all cleanup rules to a profile"""
        try:
            profile_id = profile.get("id")
            if not profile_id:
                logger.warning("Profile missing ID, skipping")
                return None
            
            data = profile.get("data", {})
            contact = data.get("contact", {})
            email_data = contact.get("email", {})
            phone_data = contact.get("phone", {})
            address_data = contact.get("address", {})
            identifier_data = data.get("identifier", {})
            job_data = data.get("job", {})
            company_data = job_data.get("company", {})
            
            # Validation
            email_main, email_status = self.validator.validate_email(email_data.get("main"))
            email_business, _ = self.validator.validate_email(email_data.get("business"))
            
            phone_main = self.validator.normalize_belgian_phone(phone_data.get("main"))
            phone_business = self.validator.normalize_belgian_phone(phone_data.get("business"))
            
            kbo = self.validator.validate_kbo(identifier_data.get("id"))
            
            postcode = self.validator.validate_postcode(address_data.get("postcode"))
            
            # Normalization
            company_name = self.validator.standardize_company_name(company_data.get("name"))
            
            # Build cleaned profile
            cleaned = {
                "id": profile_id,
                "data": {
                    "contact": {
                        "email": {
                            "main": email_main,
                            "business": email_business
                        },
                        "phone": {
                            "main": phone_main,
                            "business": phone_business
                        },
                        "address": {
                            "town": address_data.get("town", "").strip().title() if address_data.get("town") else None,
                            "postcode": postcode,
                            "street": address_data.get("street", "").strip() if address_data.get("street") else None,
                            "country": address_data.get("country", "BE").upper() if address_data.get("country") else "BE"
                        }
                    },
                    "identifier": {
                        "id": kbo
                    },
                    "job": {
                        "company": {
                            "name": company_name,
                            "size": company_data.get("size"),
                            "country": company_data.get("country", "BE").upper() if company_data.get("country") else "BE"
                        }
                    }
                },
                "traits": {
                    **profile.get("traits", {}),
                    "_cleanup_version": "1.0",
                    "_cleanup_date": datetime.now().isoformat(),
                    "_cleanup_stats": {
                        "email_valid": email_status == "valid",
                        "phone_normalized": phone_main is not None,
                        "kbo_valid": kbo is not None,
                        "postcode_valid": postcode is not None
                    }
                }
            }
            
            # Track validation failures
            if email_status != "valid":
                self.stats["validation_failures"]["email"] += 1
            if not phone_main:
                self.stats["validation_failures"]["phone"] += 1
            if not kbo:
                self.stats["validation_failures"]["kbo"] += 1
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Error cleaning profile: {e}")
            self.stats["errors"] += 1
            return None
    
    def import_profiles(self, profiles: List[Dict]) -> bool:
        """Import cleaned profiles to Tracardi"""
        if not profiles:
            return True
        
        try:
            resp = requests.post(
                f"{self.tracardi_url}/profiles/import",
                headers=self.get_auth_headers(),
                json=profiles,
                timeout=60
            )
            
            if resp.status_code == 200:
                self.stats["updated"] += len(profiles)
                return True
            else:
                logger.error(f"Import error: {resp.status_code} - {resp.text[:500]}")
                self.stats["errors"] += len(profiles)
                return False
                
        except Exception as e:
            logger.error(f"Error importing profiles: {e}")
            self.stats["errors"] += len(profiles)
            return False
    
    def process_batch(self, offset: int) -> bool:
        """Process a single batch"""
        try:
            profiles = self.fetch_batch(offset)
            if not profiles:
                return False
            
            cleaned = []
            for profile in profiles:
                cleaned_profile = self.clean_profile(profile)
                if cleaned_profile:
                    cleaned.append(cleaned_profile)
                self.stats["processed"] += 1
            
            if cleaned:
                return self.import_profiles(cleaned)
            return True
            
        except Exception as e:
            logger.error(f"Error processing batch at offset {offset}: {e}")
            return False
    
    def run(self, total_profiles: int, max_workers: int = 4) -> Dict:
        """Main processing loop"""
        self.stats["start_time"] = datetime.now().isoformat()
        batches = (total_profiles // self.batch_size) + 1
        
        logger.info(f"Starting cleanup of {total_profiles:,} profiles")
        logger.info(f"Batch size: {self.batch_size}, Workers: {max_workers}")
        logger.info(f"Total batches: {batches}")
        
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i in range(batches):
                offset = i * self.batch_size
                future = executor.submit(self.process_batch, offset)
                futures[future] = i
            
            for future in as_completed(futures):
                batch_num = futures[future]
                try:
                    success = future.result()
                    completed += 1
                    if completed % 10 == 0:
                        logger.info(f"Progress: {completed}/{batches} batches ({completed/batches*100:.1f}%)")
                        logger.info(f"Stats: {dict(self.stats)}")
                except Exception as e:
                    logger.error(f"Batch {batch_num} failed: {e}")
        
        self.stats["end_time"] = datetime.now().isoformat()
        
        # Calculate duration
        start = datetime.fromisoformat(self.stats["start_time"])
        end = datetime.fromisoformat(self.stats["end_time"])
        duration = (end - start).total_seconds()
        
        logger.info("=" * 60)
        logger.info("CLEANUP COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        logger.info(f"Processed: {self.stats['processed']:,}")
        logger.info(f"Updated: {self.stats['updated']:,}")
        logger.info(f"Errors: {self.stats['errors']:,}")
        logger.info(f"Rate: {self.stats['processed']/duration:.1f} profiles/second")
        
        return dict(self.stats)


def test_cleanup(tracardi_url: str, token: str, es_host: str, index: str):
    """Test cleanup on 5 profiles"""
    logger.info("Running test cleanup on 5 profiles...")
    
    cleaner = ProfileCleaner(es_host, tracardi_url, token, batch_size=5)
    
    # Fetch 5 profiles
    query = {
        "size": 5,
        "query": {"match_all": {}},
        "_source": True
    }
    
    resp = requests.post(f"{es_host}/_search", json=query)
    profiles = [hit.get("_source", {}) for hit in resp.json().get("hits", {}).get("hits", [])]
    
    logger.info(f"Fetched {len(profiles)} test profiles")
    
    for profile in profiles:
        logger.info(f"\nOriginal profile: {profile.get('id')}")
        cleaned = cleaner.clean_profile(profile)
        if cleaned:
            logger.info(f"Cleaned profile: {json.dumps(cleaned, indent=2, default=str)[:1000]}")


if __name__ == "__main__":
    import os
    import sys
    
    # Configuration from environment variables
    ES_HOST = os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200")
    TRACARDI_URL = os.environ["TRACARDI_API_URL"]  # No default - must be set
    TOKEN = os.environ["TRACARDI_TOKEN"]  # No default - must be set via env var
    INDEX_NAME = "09x.8504a.tracardi-profile-2026-q1"
    TOTAL_PROFILES = 516000
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_cleanup(TRACARDI_URL, TOKEN, ES_HOST, INDEX_NAME)
    else:
        cleaner = ProfileCleaner(ES_HOST, TRACARDI_URL, TOKEN, batch_size=100)
        results = cleaner.run(TOTAL_PROFILES, max_workers=4)
        
        # Save results
        with open(f"cleanup_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
            json.dump(results, f, indent=2)
