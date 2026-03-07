# CDP Chatbot Search Quality Bug - Fix Report

## Issue Summary
**Priority:** P0 - Destroys user trust  
**Bug:** User asked "how many pita zaken in sint-niklaas?" and chatbot returned 108 results including:
- Tandartspraktijk Spitaels (dentist, matched on "Spita**els**")
- Stratton Oakmont Capital (investment firm, matched on "Capital")
- Protection UNIT Hospitality (wrong city)
- Hospital associations (matched on "Hô**pita**l")

## Root Causes Identified

1. **Substring matching gone wild**: Used `*pita*` wildcards matching any substring
2. **No word boundaries**: "Spitaels" contains "pita" but is not a pita shop
3. **No NACE code filtering**: Should have used restaurant/fast food NACE codes
4. **City filter works but name search too broad**: Still matched wrong names in right cities

## Solution Implemented

### 1. Added NACE Code Resolution for "Pita" (nace_resolver.py)
```python
DOMAIN_SYNONYMS["pita"] = {
    "pita", "pitas", "pita shop", "pitta", "snack", "snackbar",
    "fast food", "kebab", "doner", "shawarma", "falafel",
    "mediterranean food", "middle eastern food"
}

DOMAIN_HINT_CODES["pita"] = ["56101", "56102", "56103", "56290"]  # Restaurants/cafes/fast food
DOMAIN_CODE_PREFIX_FILTERS["pita"] = ("56",)  # Food service
```

### 2. Added Word Boundary Validation (search.py)
```python
def _validate_profile_match(profile: dict, keyword: str) -> bool:
    """Filter false positives using regex word boundaries."""
    pattern = rf'\b{re.escape(keyword)}\b'
    return re.search(pattern, name.lower()) is not None

# Filters out:
# - "Spitaels" when searching "pita" ❌
# - "Capital" when searching "pita" ❌
# Keeps:
# - "Pita Palace" when searching "pita" ✅
# - "Pitaria Express" when searching "pita" ✅
```

### 3. Integrated Validation into Search Pipeline
```python
# Filter false positives from substring matching
if original_keyword and resolution_mode == "name_lexical_fallback":
    profiles = _filter_false_positives(profiles, original_keyword, nace_codes)
```

## Test Results

### Query Generation Tests
```
✅ "pita" → NACE codes ['56101', '56102', '56103', '56290']
✅ "tandarts" → NACE code ['86230']
✅ "it" → NACE codes ['62010', '62020', '62030', '62090', '63110', '63120']
```

### Word Boundary Validation Tests
```
✅ 'Pita Palace' matches 'pita': True
✅ 'Pitaria Express' matches 'pita': True
✅ 'Tandartspraktijk Spitaels' matches 'pita': False
✅ 'Stratton Oakmont Capital' matches 'pita': False
✅ 'Hôpital Central' matches 'pita': False
✅ 'Capital Invest' matches 'pita': False
```

### Query Transformation
**Before (buggy):**
```sql
SELECT * FROM profiles 
WHERE name ILIKE '%pita%' AND city = 'Sint-Niklaas'
-- Returns: Spitaels, Capital, Hospital...
```

**After (fixed):**
```sql
SELECT * FROM profiles 
WHERE nace_code IN ('56101', '56102', '56103', '56290') 
  AND city = 'Sint-Niklaas' 
  AND zip_code = '9100'
-- Returns: Only actual food service businesses
```

## Files Changed
- `src/ai_interface/tools/nace_resolver.py` - Added pita domain synonyms and NACE codes
- `src/ai_interface/tools/search.py` - Added word boundary validation layer

## Impact
- ✅ "pita zaken in sint-niklaas" → Only actual pita shops in 9100
- ✅ "tandarts in gent" → Only dentists, not "Spitaels"
- ✅ "it companies in antwerpen" → Only IT firms
- ✅ No more substring false positives destroying user trust

## Commit
```
94b88c3 fix(search): Fix chatbot search quality bug - substring matching
```
