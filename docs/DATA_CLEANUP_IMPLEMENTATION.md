# Data Cleanup & Enrichment Implementation Plan
## CDP Merged - Tracardi Profile Cleanup Strategy

**Document Version:** 1.0  
**Date:** 2026-02-25  
**Target:** 516,000+ existing profiles  
**Budget:** €150

---

## Executive Summary

This document outlines a comprehensive strategy for cleaning and enriching 516K+ existing Tracardi profiles containing Belgian company data (KBO/BCE numbers). The approach prioritizes **data safety** (non-destructive), **incremental processing** (batch-based), and **rollback capability**.

**Recommended Strategy:** Hybrid Approach
- **Phase 1:** Direct Elasticsearch updates for bulk field additions
- **Phase 2:** Tracardi Import API for complex merges and deduplication

---

## 1. Current Data Structure Analysis

### 1.1 Tracardi Profile Schema

Based on OpenAPI specification analysis, the profile structure is:

```
Profile
├── id (string, required) - Primary profile ID
├── primary_id (string|null) - Merged profile reference
├── metadata
│   ├── time (insert, visit timestamps)
│   ├── aux (custom metadata)
│   ├── fields (custom fields)
│   └── system (integrations, aux)
├── ids (array) - Alternative identifiers
├── operation (merge, new, segment, update flags)
├── stats (views, visits, counters)
├── traits (object - custom traits)
├── segments (array)
├── interests (object)
├── consents (object)
├── active (boolean)
├── aux (object - custom aux data)
└── data
    ├── anonymous (boolean)
    ├── pii
    │   ├── attributes
    │   ├── civil (name, birthday, gender)
    │   ├── education
    │   └── language
    ├── contact
    │   ├── email
    │   │   ├── main
    │   │   ├── private
    │   │   └── business
    │   ├── phone
    │   │   ├── main
    │   │   ├── business
    │   │   ├── mobile
    │   │   └── whatsapp
    │   ├── app (other)
    │   ├── address
    │   │   ├── town
    │   │   ├── county
    │   │   ├── country
    │   │   ├── postcode
    │   │   ├── street
    │   │   └── other
    │   └── confirmations (array)
    ├── identifier
    │   ├── id (KBO likely here)
    │   ├── pk
    │   ├── badge
    │   ├── passport
    │   ├── credit_card
    │   ├── token
    │   └── coupons
    ├── devices
    ├── media
    ├── preferences
    ├── job
    │   └── company
    │       ├── name
    │       ├── size
    │       ├── segment
    │       └── country
    ├── metrics
    └── loyalty
```

### 1.2 Key Fields for KBO Data

| KBO Data Field | Tracardi Location | Notes |
|----------------|-------------------|-------|
| KBO Number | `data.identifier.id` or `ids[]` | Primary business identifier |
| Company Name | `data.job.company.name` | Business entity name |
| Address | `data.contact.address.*` | Street, postcode, town |
| Email | `data.contact.email.business` | Business contact |
| Phone | `data.contact.phone.business` | Business phone |
| NACE Code | `traits.nace_code` | Industry classification |
| Legal Form | `traits.legal_form` | Company structure |
| Status | `metadata.status` or `traits.company_status` | Active/inactive |

### 1.3 Expected Data Quality Issues

Based on typical CDP data patterns:

| Issue | Likelihood | Impact |
|-------|------------|--------|
| Missing KBO numbers | High | Cannot deduplicate |
| Duplicate profiles | High | Inflated counts, fragmented view |
| Invalid email formats | Medium | Bounce risk |
| Inconsistent phone formats | High | Dialing issues |
| Missing addresses | Medium | Geocoding impossible |
| Null/empty fields | High | Incomplete records |
| Inconsistent company names | High | Search/dedupe issues |

---

## 2. Cleanup Strategy Options

### Option A: Tracardi Import API (Recommended for Merges)

**Endpoint:** `POST /profiles/import`

**Pros:**
- Native Tracardi integration
- Built-in validation
- Automatic profile merging
- Respects workflow triggers
- Audit trail

**Cons:**
- Slower (HTTP overhead)
- Rate limited
- Requires authentication token
- Batch size limitations

**Best For:**
- Complex deduplication with merge logic
- When workflow triggers are needed
- Smaller batches (<10K records)

### Option B: Direct Elasticsearch Update (Recommended for Bulk Fields)

**Endpoint:** `POST /{index}/_update_by_query`

**Pros:**
- Fastest execution
- No HTTP per-record overhead
- Native ES query power
- Can update millions quickly

**Cons:**
- Bypasses Tracardi business logic
- No workflow triggers
- Requires direct ES access
- Risk of data inconsistency

**Best For:**
- Adding new enrichment fields
- Bulk normalization
- Initial data fixes

### Option C: New Index + Reindex

**Process:**
1. Create new cleaned index
2. Transform data during reindex
3. Switch alias when ready

**Pros:**
- Zero downtime
- Full data transformation
- Easy rollback (keep old index)
- Can test thoroughly

**Cons:**
- Requires 2x storage
- Complex alias management
- Longest implementation time

**Best For:**
- Major schema changes
- When downtime is unacceptable
- Large-scale restructuring

### **Recommended Hybrid Approach**

1. **Phase 1 - Bulk Field Updates (ES Direct):** Add enrichment fields quickly
2. **Phase 2 - Deduplication (Tracardi API):** Merge duplicates with business logic
3. **Phase 3 - Validation (Tracardi API):** Update normalized/cleaned fields

---

## 3. Cleanup Pipeline Design

### Step 1: Deduplication

**Duplicate Detection Strategy:**

```python
# Primary key: KBO number
def find_duplicates():
    query = {
        "aggs": {
            "duplicate_kbo": {
                "terms": {
                    "field": "data.identifier.id",
                    "min_doc_count": 2,
                    "size": 10000
                }
            }
        }
    }
    # Returns KBOs with multiple profiles
```

**Merge Strategy (Keep Most Complete):**

| Field Priority | Rule |
|----------------|------|
| 1. Most fields populated | Count non-null fields |
| 2. Most recent activity | `metadata.time.visit` |
| 3. Has email | Prefer verified contact |
| 4. Has address | Better for geocoding |
| 5. Oldest creation | `metadata.time.insert` |

**Merge Logic:**
```python
def merge_profiles(primary, duplicates):
    merged = primary.copy()
    for dup in duplicates:
        # Fill missing fields from duplicates
        for field in all_fields:
            if not merged.get(field) and dup.get(field):
                merged[field] = dup[field]
        # Aggregate stats
        merged['stats']['views'] += dup['stats']['views']
        merged['stats']['visits'] += dup['stats']['visits']
        # Merge IDs list
        merged['ids'] = list(set(merged['ids'] + dup['ids']))
    return merged
```

### Step 2: Validation

#### Email Validation
```python
import re

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def validate_email(email):
    if not email:
        return None, "empty"
    if not EMAIL_REGEX.match(email):
        return None, "invalid_format"
    # DNS check (optional, costs time)
    # domain = email.split('@')[1]
    # if not has_mx_record(domain):
    #     return None, "no_mx_record"
    return email.lower().strip(), "valid"
```

#### Phone Normalization (Belgian Format)
```python
import re

def normalize_belgian_phone(phone):
    """
    Normalize to +32 XXX XX XX XX format
    """
    if not phone:
        return None
    
    # Remove all non-digits
    digits = re.sub(r'\D', '', phone)
    
    # Handle Belgian numbers
    if digits.startswith('32'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = digits[1:]
    elif digits.startswith('+'):
        digits = digits[3:] if digits[2] == '32' else digits[1:]
    
    # Validate length (8-9 digits for Belgian)
    if len(digits) < 8 or len(digits) > 10:
        return None
    
    # Format: +32 XXX XX XX XX
    return f"+32 {digits[:3]} {digits[3:5]} {digits[5:7]} {digits[7:]}"
```

#### Postal Code Validation (Belgium)
```python
VALID_BE_POSTCODES = set(range(1000, 10000))  # 1000-9999

def validate_postcode(postcode):
    """
    Belgian postcodes: 1000-9999
    """
    if not postcode:
        return None
    
    digits = re.sub(r'\D', '', str(postcode))
    
    if len(digits) == 3:
        # Might be missing leading zero (Luxembourg province)
        digits = '6' + digits  # 6xxx for Luxembourg
    
    try:
        code = int(digits)
        if 1000 <= code <= 9999:
            return str(code)
    except ValueError:
        pass
    
    return None
```

#### KBO Number Validation
```python
def validate_kbo(kbo):
    """
    Validate Belgian KBO/BCE number (10 digits with checksum)
    Format: XXXX.XXX.XXX or XXXXXXXXXX
    """
    if not kbo:
        return None
    
    # Remove separators
    digits = re.sub(r'\D', '', str(kbo))
    
    # Must be 10 digits
    if len(digits) != 10:
        return None
    
    # Checksum validation (modulo 97)
    try:
        number = int(digits[:9])
        checksum = int(digits[9])
        calculated = number % 97
        if calculated == checksum or calculated == 0 and checksum == 97:
            return digits
    except ValueError:
        pass
    
    return None
```

### Step 3: Normalization

#### Company Name Standardization
```python
import re

COMPANY_SUFFIXES = [
    'bv', 'b.v', 'b.v.', 'bvba', 'b.v.b.a', 'b.v.b.a.',
    'nv', 'n.v', 'n.v.', 'vzw', 'v.z.w', 'v.z.w.',
    'cv', 'c.v', 'c.v.', 'cvba', 'c.v.b.a', 'c.v.b.a.',
    'comm.v', 'comm. v', 'ec', 'gmbh', 'ltd', 'llc'
]

def standardize_company_name(name):
    if not name:
        return None
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    # Title case (keep known acronyms uppercase)
    words = name.lower().split()
    standardized = []
    for word in words:
        # Keep known acronyms uppercase
        if word.upper() in ['SA', 'SAS', 'SC', 'SCRL', 'SPRL']:
            standardized.append(word.upper())
        else:
            standardized.append(word.capitalize())
    
    name = ' '.join(standardized)
    
    # Normalize suffixes
    for suffix in COMPANY_SUFFIXES:
        pattern = rf'\b{suffix}\b\.?$'
        if re.search(pattern, name, re.IGNORECASE):
            name = re.sub(pattern, 'BV', name, flags=re.IGNORECASE)
            break
    
    return name
```

#### Address Normalization
```python
def normalize_address(street, postcode, town, country='BE'):
    """
    Standardize address components
    """
    street = street.strip() if street else None
    town = town.strip().title() if town else None
    country = country.upper() if country else 'BE'
    
    # Validate and normalize postcode
    postcode = validate_postcode(postcode)
    
    return {
        'street': street,
        'postcode': postcode,
        'town': town,
        'country': country
    }
```

#### NACE Code Formatting
```python
def format_nace(nace):
    """
    Normalize NACE code to XXXXXX format
    """
    if not nace:
        return None
    
    digits = re.sub(r'\D', '', str(nace))
    
    # NACE should be 4-6 digits
    if len(digits) < 4 or len(digits) > 6:
        return None
    
    # Pad to 6 digits if needed
    return digits.zfill(6)
```

### Step 4: Enrichment (Phase 2)

#### Geocoding Strategy
```python
# Use OpenStreetMap Nominatim (free, rate-limited)
# Or Google Geocoding API (paid, more accurate)

def geocode_address(address):
    """
    Convert address to lat/lng
    """
    query = f"{address['street']}, {address['postcode']} {address['town']}, Belgium"
    
    # Implementation depends on chosen provider
    # Returns: {'lat': 50.85, 'lng': 4.35, 'accuracy': 'street'}
    pass
```

#### AI Description Generation
```python
# Use local LLM or API (within budget)
def generate_company_description(company_name, nace_code):
    """
    Generate business description based on name and NACE
    """
    # Use cached NACE descriptions + AI for enhancement
    pass
```

#### Website Discovery
```python
def discover_website(company_name, kbo):
    """
    Search for company website
    """
    # Search strategy:
    # 1. Try common patterns: www.{company}.be/com
    # 2. Google/Bing search (respect robots)
    # 3. KBO public data cross-reference
    pass
```

---

## 4. Implementation Plan

### Phase 0: Setup & Validation (Day 1)

```bash
# 1. Verify ES connectivity (from Tracardi server)
curl -s http://localhost:9200/_cluster/health

# 2. Get exact index name
INDEX_NAME=$(curl -s http://localhost:9200/_cat/indices | grep profile | awk '{print $3}')
echo "Profile index: $INDEX_NAME"

# 3. Get document count
curl -s http://localhost:9200/${INDEX_NAME}/_count

# 4. Get mapping
curl -s http://localhost:9200/${INDEX_NAME}/_mapping > profile_mapping.json
```

### Phase 1: Data Profiling (Day 1-2)

```python
#!/usr/bin/env python3
"""
profile_analyzer.py - Analyze existing profile data quality
"""
import requests
import json
from collections import Counter

class ProfileAnalyzer:
    def __init__(self, es_host, index_name):
        self.es_host = es_host
        self.index = index_name
    
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
        resp = requests.post(f"{self.es_host}/{self.index}/_search", json=query)
        return resp.json()
    
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
        resp = requests.post(f"{self.es_host}/{self.index}/_search", json=query)
        return resp.json()
    
    def sample_profiles(self, n=100):
        """Get sample profiles for inspection"""
        query = {
            "size": n,
            "query": {"match_all": {}},
            "_source": True
        }
        resp = requests.post(f"{self.es_host}/{self.index}/_search", json=query)
        return resp.json()

# Usage
if __name__ == "__main__":
    analyzer = ProfileAnalyzer("http://localhost:9200", "09x.8504a.tracardi-profile-2026-q1")
    
    # Check KBO field population
    print("KBO Field Stats:")
    print(analyzer.get_field_stats("data.identifier.id"))
    
    # Check email population
    print("Email Field Stats:")
    print(analyzer.get_field_stats("data.contact.email.main"))
    
    # Find duplicate KBOs
    print("Duplicate KBOs:")
    print(analyzer.find_duplicates("data.identifier.id"))
```

### Phase 2: Test Batch (Day 2-3)

```python
#!/usr/bin/env python3
"""
cleanup_test.py - Test cleanup on 100 profiles
"""
import requests
import json

class ProfileCleaner:
    def __init__(self, tracardi_url, token):
        self.url = tracardi_url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def get_profiles(self, limit=100):
        """Fetch test batch"""
        resp = requests.post(
            f"{self.url}/profile/select",
            headers=self.headers,
            json={"limit": limit}
        )
        return resp.json()
    
    def update_profile(self, profile_id, updates):
        """Update single profile via Tracardi API"""
        resp = requests.post(
            f"{self.url}/profiles/import",
            headers=self.headers,
            json=[{"id": profile_id, **updates}]
        )
        return resp.json()

# Test on 100 profiles, validate, measure timing
```

### Phase 3: Full Cleanup (Day 3-5)

```python
#!/usr/bin/env python3
"""
bulk_cleanup.py - Full production cleanup
"""
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BulkProfileCleaner:
    def __init__(self, es_host, tracardi_url, token, batch_size=100):
        self.es_host = es_host
        self.tracardi_url = tracardi_url
        self.token = token
        self.batch_size = batch_size
        self.stats = {
            "processed": 0,
            "updated": 0,
            "errors": 0,
            "duplicates_found": 0,
            "duplicates_merged": 0
        }
    
    def process_batch(self, profiles):
        """Process a batch of profiles"""
        cleaned = []
        for profile in profiles:
            try:
                cleaned_profile = self.clean_profile(profile)
                cleaned.append(cleaned_profile)
                self.stats["processed"] += 1
            except Exception as e:
                logger.error(f"Error cleaning profile {profile.get('id')}: {e}")
                self.stats["errors"] += 1
        
        # Send to Tracardi
        return self.import_profiles(cleaned)
    
    def clean_profile(self, profile):
        """Apply all cleanup rules to a profile"""
        # Validation
        email = self.validate_email(profile.get("data", {}).get("contact", {}).get("email", {}).get("main"))
        phone = self.normalize_phone(profile.get("data", {}).get("contact", {}).get("phone", {}).get("main"))
        kbo = self.validate_kbo(profile.get("data", {}).get("identifier", {}).get("id"))
        
        # Normalization
        company_name = self.standardize_company_name(
            profile.get("data", {}).get("job", {}).get("company", {}).get("name")
        )
        
        # Build update
        updates = {
            "id": profile["id"],
            "data": {
                "contact": {
                    "email": {"main": email},
                    "phone": {"main": phone}
                },
                "identifier": {"id": kbo},
                "job": {
                    "company": {"name": company_name}
                }
            },
            "traits": {
                "_cleanup_version": "1.0",
                "_cleanup_date": "2026-02-25"
            }
        }
        
        return updates
    
    def import_profiles(self, profiles):
        """Import cleaned profiles to Tracardi"""
        resp = requests.post(
            f"{self.tracardi_url}/profiles/import",
            headers={"Authorization": f"Bearer {self.token}"},
            json=profiles
        )
        if resp.status_code == 200:
            self.stats["updated"] += len(profiles)
        else:
            self.stats["errors"] += len(profiles)
            logger.error(f"Import error: {resp.text}")
        return resp.json()
    
    def run(self, total_profiles):
        """Main processing loop"""
        batches = (total_profiles // self.batch_size) + 1
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for i in range(batches):
                # Fetch batch from ES
                profiles = self.fetch_batch(i * self.batch_size)
                future = executor.submit(self.process_batch, profiles)
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Batch error: {e}")
        
        return self.stats

if __name__ == "__main__":
    cleaner = BulkProfileCleaner(
        es_host="http://localhost:9200",
        tracardi_url="http://52.148.232.140:8686",
        token="YOUR_TOKEN_HERE",
        batch_size=100
    )
    stats = cleaner.run(total_profiles=516000)
    print(json.dumps(stats, indent=2))
```

### Phase 4: Deduplication (Day 5-7)

```python
#!/usr/bin/env python3
"""
deduplicate.py - Merge duplicate profiles by KBO
"""
import requests

class ProfileDeduplicator:
    def __init__(self, es_host, tracardi_url, token):
        self.es_host = es_host
        self.tracardi_url = tracardi_url
        self.token = token
    
    def find_duplicate_groups(self):
        """Find all KBOs with multiple profiles"""
        query = {
            "size": 0,
            "aggs": {
                "duplicate_kbos": {
                    "terms": {
                        "field": "data.identifier.id",
                        "min_doc_count": 2,
                        "size": 10000
                    },
                    "aggs": {
                        "profiles": {
                            "top_hits": {
                                "size": 10,
                                "_source": True
                            }
                        }
                    }
                }
            }
        }
        resp = requests.post(f"{self.es_host}/09x.8504a.tracardi-profile-2026-q1/_search", json=query)
        return resp.json()
    
    def merge_duplicate_group(self, kbo, profiles):
        """Merge profiles with same KBO"""
        # Select primary (most complete)
        primary = max(profiles, key=self.completeness_score)
        
        # Merge data from others
        merged = primary.copy()
        for profile in profiles:
            if profile["id"] == primary["id"]:
                continue
            merged = self.merge_two_profiles(merged, profile)
        
        # Update primary
        self.update_profile(merged)
        
        # Delete duplicates
        for profile in profiles:
            if profile["id"] != primary["id"]:
                self.delete_profile(profile["id"])
    
    def completeness_score(self, profile):
        """Calculate data completeness score"""
        score = 0
        data = profile.get("data", {})
        
        # Email: +10
        if data.get("contact", {}).get("email", {}).get("main"):
            score += 10
        
        # Phone: +10
        if data.get("contact", {}).get("phone", {}).get("main"):
            score += 10
        
        # Address: +15
        if data.get("contact", {}).get("address", {}).get("street"):
            score += 15
        
        # Company name: +5
        if data.get("job", {}).get("company", {}).get("name"):
            score += 5
        
        # Visits: +1 per visit
        score += profile.get("stats", {}).get("visits", 0)
        
        return score
    
    def merge_two_profiles(self, primary, secondary):
        """Merge secondary into primary"""
        # Fill missing fields
        for key, value in secondary.get("data", {}).items():
            if not primary.get("data", {}).get(key):
                primary["data"][key] = value
        
        # Aggregate stats
        primary["stats"]["visits"] += secondary.get("stats", {}).get("visits", 0)
        primary["stats"]["views"] += secondary.get("stats", {}).get("views", 0)
        
        # Merge IDs
        primary["ids"] = list(set(primary.get("ids", []) + secondary.get("ids", [])))
        
        return primary
```

---

## 5. Rollback Strategy

### Pre-Cleanup Backup

```bash
#!/bin/bash
# backup.sh - Create ES snapshot before cleanup

# 1. Create snapshot repository (if not exists)
curl -X PUT "localhost:9200/_snapshot/cleanup_backup" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "fs",
    "settings": {
      "location": "/backup/elasticsearch"
    }
  }'

# 2. Take snapshot
curl -X PUT "localhost:9200/_snapshot/cleanup_backup/pre_cleanup_$(date +%Y%m%d)"

# 3. Also export sample for comparison
curl -X POST "localhost:9200/09x.8504a.tracardi-profile-2026-q1/_search" \
  -H "Content-Type: application/json" \
  -d '{"size": 1000, "query": {"match_all": {}}}' \
  > sample_backup_$(date +%Y%m%d).json
```

### Rollback Procedure

```bash
#!/bin/bash
# rollback.sh - Restore from snapshot

SNAPSHOT_NAME="pre_cleanup_20260225"

curl -X POST "localhost:9200/_snapshot/cleanup_backup/${SNAPSHOT_NAME}/_restore"
```

### Incremental Safety

```python
# Mark profiles during cleanup for easy rollback
{
    "traits": {
        "_cleanup_version": "1.0",
        "_cleanup_date": "2026-02-25",
        "_cleanup_batch": 1
    }
}

# To rollback a batch:
# 1. Find all profiles with cleanup marker
# 2. Restore from backup for those IDs only
```

---

## 6. Performance Estimates

### Time Estimates (516K profiles)

| Phase | Method | Rate | Time |
|-------|--------|------|------|
| Profiling | ES Queries | 10K/s | ~1 minute |
| Test (100) | Tracardi API | 10/s | ~10 seconds |
| Full Cleanup | Tracardi API | 50/s | ~2.9 hours |
| Full Cleanup | ES Direct | 1000/s | ~9 minutes |
| Deduplication | Mixed | 100 merges/min | ~2 hours |
| **Total** | | | **4-6 hours** |

### Resource Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 4GB | 8GB |
| Disk (backup) | 5GB | 10GB |
| Network | 10 Mbps | 100 Mbps |

### Batch Size Optimization

```python
# Test different batch sizes
batch_sizes = [10, 25, 50, 100, 250]
results = {}

for size in batch_sizes:
    start = time.time()
    process_batch(size)
    duration = time.time() - start
    results[size] = {
        "total_time": duration,
        "per_record": duration / size
    }

# Choose batch size with lowest per-record time
optimal_batch = min(results, key=lambda x: results[x]["per_record"])
```

---

## 7. Cost Analysis

### Within €150 Budget

| Item | Cost | Notes |
|------|------|-------|
| Compute (VM) | €0 | Use existing Tracardi server |
| Storage (backup) | €0 | Local disk sufficient |
| Geocoding API | €0 | OpenStreetMap (free) |
| AI/LLM API | €0 | Use local Ollama instance |
| **Total** | **€0** | **Well within budget** |

### Optional Upgrades (if budget allows)

| Item | Cost | Benefit |
|------|------|---------|
| Google Geocoding | ~€50 | Better accuracy |
| OpenAI API | ~€30 | Better AI descriptions |
| Additional VM | ~€70 | Parallel processing |

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Authentication issues** | High | Blocks all work | Verify credentials early; have ES direct access as fallback |
| **API rate limiting** | Medium | Slows processing | Implement exponential backoff; use ES direct for bulk |
| **Data corruption** | Low | Severe | Full backup before; test on 100 profiles; incremental approach |
| **Duplicate detection errors** | Medium | Data loss | Soft delete first; 30-day retention; manual review option |
| **Network interruptions** | Low | Incomplete job | Resume capability; batch tracking; idempotent updates |
| **Validation errors** | Medium | Bad data | Validation before update; reject invalid; manual queue |
| **ES cluster overload** | Low | Downtime | Process during low-traffic; monitor cluster health |

---

## 9. Monitoring & Validation

### Progress Tracking

```python
def log_progress(stats):
    """Log progress to file for monitoring"""
    with open("cleanup_progress.jsonl", "a") as f:
        f.write(json.dumps({
            "timestamp": datetime.now().isoformat(),
            **stats
        }) + "\n")

# Watch with: tail -f cleanup_progress.jsonl | jq .
```

### Validation Queries

```bash
# Check cleanup markers
curl -X POST "localhost:9200/09x.8504a.tracardi-profile-2026-q1/_search" -H "Content-Type: application/json" -d '{
  "size": 0,
  "aggs": {
    "by_cleanup_version": {
      "terms": {"field": "traits._cleanup_version"}
    }
  }
}'

# Check duplicate KBO count after
curl -X POST "localhost:9200/09x.8504a.tracardi-profile-2026-q1/_search" -H "Content-Type: application/json" -d '{
  "size": 0,
  "aggs": {
    "duplicate_kbos": {
      "terms": {
        "field": "data.identifier.id",
        "min_doc_count": 2
      }
    }
  }
}'
```

---

## 10. Key Questions Answered

### 1. What's the current profile structure?
**Answer:** Tracardi uses a nested JSON structure with `data.contact`, `data.identifier`, `data.job.company`, and `traits` as key containers for KBO data.

### 2. What fields are missing/populated?
**Answer:** Requires Phase 1 profiling, but typically:
- KBO: ~70% populated (estimated)
- Email: ~40% populated
- Phone: ~30% populated  
- Full address: ~25% populated

### 3. How many duplicates exist?
**Answer:** Requires Phase 1 profiling, but typically 5-15% duplicates in B2B data = **25,000-75,000 duplicates**.

### 4. What's the best update strategy?
**Answer:** Hybrid approach:
- ES direct for bulk field additions (fast)
- Tracardi API for deduplication (respects business logic)

### 5. How long will cleanup take?
**Answer:** Estimated **4-6 hours** for 516K profiles:
- Profiling: 1 hour
- Cleanup: 3 hours
- Deduplication: 2 hours

### 6. What's the resource cost?
**Answer:** **€0** - can be done on existing infrastructure with open-source tools.

---

## 11. Next Steps

1. **Verify Tracardi credentials** - Test authentication
2. **Run Phase 1 profiling** - Get actual data quality metrics
3. **Execute test batch** - Validate on 100 profiles
4. **Schedule full cleanup** - Low-traffic window
5. **Execute with monitoring** - Track progress
6. **Validate results** - Run post-cleanup checks
7. **Document learnings** - Update this plan

---

## Appendix A: Authentication Setup

```python
# Get Tracardi token
def get_token(username, password):
    resp = requests.post(
        "http://52.148.232.140:8686/user/token",
        data={
            "grant_type": "password",
            "username": username,
            "password": password
        }
    )
    return resp.json().get("access_token")
```

## Appendix B: Elasticsearch Index Access

```bash
# From Tracardi server (SSH required)
ssh user@52.148.232.140
curl -s http://localhost:9200/_cat/indices
```

## Appendix C: Troubleshooting

| Issue | Solution |
|-------|----------|
| "Not authenticated" | Verify credentials; check token expiry |
| Connection timeout | Check firewall; verify ES is running |
| Batch failures | Reduce batch size; add retry logic |
| Memory errors | Process smaller batches; add pagination |
| Duplicate merge conflicts | Manual review queue; conflict resolution rules |

---

*Document created: 2026-02-25*  
*Version: 1.0*  
*Status: Ready for Phase 1 execution*
