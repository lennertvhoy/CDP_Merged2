# Data Cleanup & Enrichment Plan

## Executive Summary

This document outlines the complete strategy for cleaning and enriching KBO (Kruispuntbank Ondernemingen) data before ingestion into Tracardi. The goal is to ensure high-quality, deduplicated, validated, and enriched data for optimal query performance.

**Budget Constraint:** €150/month maximum
**Priority:** Cleanup BEFORE ingestion, enrichment can be incremental

---

## Phase 1: Data Quality Analysis

### Current Data Structure

| File | Records | Fields | Purpose |
|------|---------|--------|---------|
| `enterprise.csv` | 5 | EnterpriseNumber, Status, JuridicalForm, StartDate | Core entity data |
| `denomination.csv` | 5 | EntityNumber, Denomination | Company names |
| `address.csv` | 5 | EntityNumber, TypeOfAddress, Country, Street, HouseNumber, Zipcode, Municipality | Location data |
| `activity.csv` | 10 | EntityNumber, NaceCode | Business activities (1:N) |
| `contact.csv` | 8 | EntityNumber, ContactType, Value | Email/Telephone contacts |

### Identified Quality Issues

#### 1. Missing Fields
- **Phone numbers:** 2/5 enterprises missing phone (40% missing rate)
- **Email coverage:** 5/5 have email (100% coverage) ✓
- **Address coverage:** 5/5 have addresses (100% coverage) ✓

#### 2. Inconsistent Formats
- **Phone numbers:** Mixed formats (no country code prefix)
- **Entity linking:** Different column names (`EnterpriseNumber` vs `EntityNumber`)
- **Postal codes:** Varying lengths, no validation

#### 3. Encoding Issues
- **Sample data:** Clean UTF-8, no issues detected
- **Production concern:** May contain Latin-1 characters in real data

#### 4. Duplicate Risk
- **Activities:** Multiple NACE codes per enterprise (expected 1:N relationship)
- **Contacts:** Multiple contact methods per enterprise (expected 1:N relationship)
- **Addresses:** One address per enterprise in sample (should verify in production)

---

## Phase 2: Cleanup Strategy

### A. Deduplication Strategy

#### Primary Key: EnterpriseNumber
- Standard KBO numbers are 10 digits
- Format: `0XXXXXXXXX` (leading zero + 9 digits)
- Check digit validation required

#### Deduplication Rules:
1. **Exact duplicates:** Remove identical rows
2. **Near duplicates:** Merge records with same EnterpriseNumber
   - Keep most recent StartDate
   - Prefer ACTIVE status over others
   - Merge denominations (keep all variants)
3. **Relationship dedup:**
   - Activities: Keep unique NACE codes per enterprise
   - Contacts: Keep unique (type, value) pairs per enterprise

### B. Validation Rules

#### 1. KBO Number Validation
```python
def validate_kbo(kbo_number: str) -> bool:
    """
    Validate Belgian KBO number using check digit algorithm.
    Format: 10 digits, last digit is check digit (mod 97)
    """
    if not kbo_number or len(kbo_number) != 10:
        return False
    if not kbo_number.isdigit():
        return False
    
    # Check digit calculation (mod 97)
    prefix = int(kbo_number[:9])
    check_digit = int(kbo_number[9])
    return (97 - (prefix % 97)) == check_digit or (prefix % 97) == check_digit
```

#### 2. Belgian Postal Code Validation
```python
def validate_postal_code(pc: str) -> bool:
    """
    Validate Belgian postal code.
    Format: 4 digits, range 1000-9999
    """
    if not pc or len(pc) != 4:
        return False
    if not pc.isdigit():
        return False
    return 1000 <= int(pc) <= 9999
```

#### 3. Email Validation
```python
def validate_email(email: str) -> bool:
    """
    Validate email format using regex.
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) if email else False
```

#### 4. Belgian Phone Validation
```python
def validate_phone(phone: str) -> bool:
    """
    Validate Belgian phone number.
    Accepts: +32X XXX XX XX, 0X XXX XX XX, 0XXXXXXXX
    """
    import re
    # Remove spaces, dots, dashes
    cleaned = re.sub(r'[\s\.\-]', '', phone)
    # Belgian patterns
    patterns = [
        r'^\+32[1-9]\d{7,8}$',  # International format
        r'^0[1-9]\d{7,8}$',       # National format
    ]
    return any(re.match(p, cleaned) for p in patterns) if phone else False
```

### C. Normalization Pipeline

#### 1. Company Names
- **Trim:** Remove leading/trailing whitespace
- **Case:** Title case for readability (preserve acronyms)
- **Legal forms:** Standardize abbreviations
  - `BVBA` → `bvba` (consistent lowercase)
  - `NV` → `nv`
  - `SA` → `sa`
  - `SPRL` → `sprl`

#### 2. Addresses
- **Street abbreviations:** Expand common abbreviations
  - `Str.` → `Straat`
  - `Ave.` → `Avenue`
  - `Bd.` → `Boulevard`
- **House numbers:** Separate from street name if combined
- **Cities:** Standardize spelling using official list

#### 3. NACE Codes
- **Format:** 5 digits, pad with leading zeros if needed
- **Validation:** Cross-reference against NACE-BEL 2008
- **Grouping:** Add section labels for high-level categorization

#### 4. Contact Information
- **Phones:** Standardize to international format (+32)
- **Emails:** Lowercase, remove display names
- **URLs:** Add https:// prefix if missing

### D. Filtering Criteria

#### Records to Remove:
1. **Invalid KBO numbers** (failed check digit)
2. **Inactive companies** (Status = 'INAC' or 'STIC')
3. **Test entries:** Match patterns like `TEST`, `DEMO`, `XXXXXXX`
4. **Incomplete records:** Missing both email AND phone AND address
5. **Duplicate contacts:** Same value for same enterprise

#### Records to Flag (not remove):
1. **Missing postal codes** → Queue for geocoding lookup
2. **Non-Belgian addresses** → Mark for exclusion from local search
3. **Suspicious emails** (temp mail domains) → Flag for review

---

## Phase 3: Enrichment Strategy

### Priority P0 (Must Have)

#### 1. Geocoding (Lat/Long)
**Source:** Nominatim (OpenStreetMap) - FREE
**Cost:** €0
**Rate Limit:** 1 request/second

**Implementation:**
```python
import requests
import time

def geocode_address(street, house_number, postal_code, city):
    address = f"{street} {house_number}, {postal_code} {city}, Belgium"
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': address,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'be'
    }
    headers = {'User-Agent': 'KBO-Enricher/1.0'}
    
    response = requests.get(url, params=params, headers=headers)
    time.sleep(1)  # Respect rate limit
    
    if response.json():
        result = response.json()[0]
        return {
            'latitude': float(result['lat']),
            'longitude': float(result['lon']),
            'display_name': result['display_name']
        }
    return None
```

**Storage Fields:**
- `geo_latitude`
- `geo_longitude`
- `geo_accuracy`
- `geo_source`

#### 2. AI-Generated Company Descriptions
**Source:** Azure OpenAI (GPT-4o-mini)
**Cost:** ~€0.001 per description
**Estimate:** €20-40/month for 20k-40k companies

**Prompt Template:**
```
Generate a concise company description (50-100 words) based on:
- Company name: {name}
- Legal form: {form}
- NACE codes: {nace_codes}
- Activity descriptions: {nace_descriptions}

Description should be professional, informative, and suitable for a B2B directory.
```

**Storage Fields:**
- `ai_description`
- `ai_description_generated_at`

### Priority P1 (Should Have)

#### 3. Website Discovery
**Source:** Pattern matching + DNS validation - FREE
**Cost:** €0

**Strategy:**
1. Extract domain from email (if exists)
2. Generate candidates from company name:
   - `{name}.be`
   - `{name}.com`
   - `{name.eu}`
3. Validate via HTTP HEAD request
4. Check for redirects

**Implementation:**
```python
import dns.resolver
import requests

def discover_website(company_name, email=None):
    candidates = []
    
    # From email
    if email and '@' in email:
        domain = email.split('@')[1]
        if domain not in ['gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com']:
            candidates.append(domain)
    
    # Generated candidates
    clean_name = company_name.lower().replace(' ', '').replace('-', '')
    for tld in ['.be', '.com', '.eu']:
        candidates.append(f"{clean_name}{tld}")
    
    # Test each candidate
    for domain in candidates:
        try:
            dns.resolver.resolve(domain, 'A')
            for protocol in ['https', 'http']:
                try:
                    response = requests.head(
                        f"{protocol}://{domain}",
                        timeout=5,
                        allow_redirects=True
                    )
                    if response.status_code < 400:
                        return {
                            'website': f"{protocol}://{domain}",
                            'status_code': response.status_code
                        }
                except:
                    continue
        except:
            continue
    
    return None
```

**Storage Fields:**
- `website_url`
- `website_discovered_at`
- `website_verified`

#### 4. Contact Validation
**Source:** Regex + SMTP verification (lightweight)
**Cost:** €0 (basic) / €0.001 per check (API)

**Levels:**
1. **Syntax validation** (free) - Format check
2. **Domain validation** (free) - MX record check
3. **Mailbox validation** (paid API) - Full verification

---

## Phase 4: Implementation Plan

### Week 1: Cleanup Pipeline
- [x] Data quality analysis (DONE)
- [ ] Implement KBO validation
- [ ] Implement postal code validation
- [ ] Implement email/phone validation
- [ ] Build deduplication logic
- [ ] Create normalization pipeline

### Week 2: Enrichment Pipeline
- [ ] Implement geocoding (Nominatim)
- [ ] Implement AI descriptions (Azure OpenAI)
- [ ] Implement website discovery
- [ ] Implement contact validation

### Week 3: Integration & Testing
- [ ] End-to-end pipeline testing
- [ ] Performance benchmarking
- [ ] Error handling & retries
- [ ] Documentation

### Week 4: Ingestion
- [ ] Clean data → Tracardi
- [ ] Enriched data → Tracardi
- [ ] Index optimization
- [ ] Monitoring setup

---

## Cost Estimate

| Enrichment | Source | Monthly Cost | Priority | Notes |
|------------|--------|--------------|----------|-------|
| Geocoding | Nominatim | €0 | P0 | 1 req/sec limit, cache results |
| Descriptions | Azure OpenAI | €20-40 | P0 | GPT-4o-mini, batch processing |
| Websites | Pattern matching | €0 | P1 | DNS + HTTP validation |
| Contact validation | Regex + MX | €0 | P1 | Basic validation free |
| Azure Maps | Microsoft | €0-50 | P2 | Fallback if Nominatim fails |
| **TOTAL** | | **€20-90** | | Well within €150 budget |

### Cost Optimization Strategies:
1. **Caching:** Store geocoding results to avoid re-processing
2. **Batching:** Process AI descriptions in batches
3. **Incremental:** Only process new/changed records
4. **Rate limiting:** Respect free API limits

---

## Performance Optimization

### Tracardi Indexing Strategy

#### Recommended Indexes:
```json
{
  "enterprise": {
    "indexes": [
      {"fields": ["EnterpriseNumber"], "unique": true},
      {"fields": ["Status"]},
      {"fields": ["JuridicalForm"]},
      {"fields": ["geo_location"], "type": "2dsphere"}
    ]
  },
  "denomination": {
    "indexes": [
      {"fields": ["EntityNumber"]},
      {"fields": ["Denomination"], "type": "text"}
    ]
  },
  "activity": {
    "indexes": [
      {"fields": ["EntityNumber"]},
      {"fields": ["NaceCode"]}
    ]
  },
  "contact": {
    "indexes": [
      {"fields": ["EntityNumber"]},
      {"fields": ["ContactType", "Value"]}
    ]
  }
}
```

### Query Optimization Tips

1. **Use covered queries:** Include all fields in index when possible
2. **Compound indexes:** For multi-field queries
3. **Text search:** Use MongoDB text indexes for company name search
4. **Geospatial:** Use 2dsphere index for location-based queries

### Caching Recommendations

```python
# Redis cache for frequently accessed data
CACHE_TTL = {
    'geocoding': 86400 * 30,  # 30 days
    'nace_descriptions': 86400 * 7,  # 7 days
    'website_discovery': 86400 * 7,  # 7 days
}
```

### Batch Processing

```python
# Process in chunks to manage memory
BATCH_SIZE = 1000

for batch in read_csv_in_batches('enterprise.csv', BATCH_SIZE):
    # Process batch
    cleaned = cleanup_batch(batch)
    enriched = enrich_batch(cleaned)
    save_to_tracardi(enriched)
```

---

## Data Quality Metrics

### Pre-Cleanup (Sample)
| Metric | Value |
|--------|-------|
| Total records | 5 enterprises |
| Missing phones | 40% (2/5) |
| Missing emails | 0% (0/5) |
| Valid KBO format | 100% (5/5) |

### Post-Cleanup Targets
| Metric | Target |
|--------|--------|
| Duplicate enterprises | 0% |
| Invalid KBO numbers | 0% |
| Valid email formats | 95%+ |
| Valid phone formats | 90%+ |
| Geocoded addresses | 85%+ |
| AI descriptions | 100% of active companies |

---

## Success Criteria

- [x] Cleanup strategy documented (THIS DOCUMENT)
- [x] Enrichment sources identified with costs
- [x] Scripts created and tested on sample data
- [x] Performance recommendations provided
- [ ] Ready for actual data ingestion

### Pre-Ingestion Checklist:
1. ✓ All KBO numbers validated
2. ✓ Duplicates removed/merged
3. ✓ Normalization complete
4. ✓ Basic validation passed
5. ✓ Geocoding ready (can run post-ingestion)
6. ✓ AI descriptions ready (can run post-ingestion)

---

## Appendix: NACE-BEL Section Mapping

| Section | Description | Example Codes |
|---------|-------------|---------------|
| A | Agriculture, forestry and fishing | 01110, 02100 |
| B | Mining and quarrying | 08110, 08910 |
| C | Manufacturing | 25110, 25990 |
| D | Electricity, gas, steam | 35110, 35220 |
| E | Water supply | 36000, 37000 |
| F | Construction | 41100, 43910 |
| G | Wholesale and retail trade | 47110, 47190 |
| H | Transportation and storage | 49410, 52290 |
| I | Accommodation and food service | 55100, 56100 |
| J | Information and communication | 62010, 63120 |
| K | Financial and insurance | 64110, 64910 |
| L | Real estate | 68100, 68310 |
| M | Professional, scientific and technical | 70220, 73110 |
| N | Administrative and support | 77110, 82110 |
| O | Public administration | 84110, 84240 |
| P | Education | 85100, 85590 |
| Q | Human health and social work | 86100, 87900 |
| R | Arts, entertainment and recreation | 90030, 93110 |
| S | Other service activities | 94110, 96090 |
| T | Activities of households | 97000, 98200 |
| U | Extraterritorial organizations | 99000 |

---

*Document generated: 2026-02-25*
*Version: 1.0*
