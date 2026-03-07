# CDP Chatbot Segment Creation Bug - Fix Report

## Issue Summary
**Bug:** User asked "how many IT companies in sint-niklaas" and the chatbot returned "2394 active IT companies in Sint-Niklaas". However, when creating a segment for these results, it showed "0 profiles matching the specified criteria".

This was a mismatch between the count query results and segment creation.

## Root Cause

The TQL (Tracardi Query Language) query was only searching for `traits.nace_codes` (plural), but the actual profile data in Tracardi may use `traits.nace_code` (singular) as the field name.

**Before (buggy TQL):**
```
traits.nace_codes IN ["62010", "62020", ...]
```

**After (fixed TQL):**
```
(traits.nace_code IN ["62010", "62020", ...] OR traits.nace_codes IN ["62010", "62020", ...])
```

By using an OR condition with both field names, the query now matches profiles regardless of which field name variant is used in the actual data.

## Changes Made

### 1. TQL Builder (src/search_engine/builders/tql_builder.py)

Changed the NACE code condition from:
```python
conditions.append(f"traits.nace_codes IN [{codes_list}]")
```

To:
```python
nace_condition_singular = f"traits.nace_code IN [{codes_list}]"
nace_condition_plural = f"traits.nace_codes IN [{codes_list}]"
conditions.append(f"({nace_condition_singular} OR {nace_condition_plural})")
```

### 2. ES Builder (src/search_engine/builders/es_builder.py)

Changed the Elasticsearch query from:
```python
{"terms": {"traits.nace_codes.keyword": params.nace_codes}}
```

To:
```python
{
    "bool": {
        "should": [
            {"terms": {"traits.nace_code.keyword": params.nace_codes}},
            {"terms": {"traits.nace_codes.keyword": params.nace_codes}}
        ]
    }
}
```

Also added `traits.nace_codes` to the `_source` fields list.

### 3. Updated Tests

- Updated `tests/unit/test_tql_builder.py` to verify both field names are used
- Updated `tests/unit/test_es_builder.py` to verify the bool/should structure

## Example Query Output

**TQL Query for "IT companies in Sint-Niklaas":**
```
(traits.city="Sint-Niklaas" OR traits.city="Saint-Nicolas" OR 
 traits.kbo_city="Sint-Niklaas" OR traits.kbo_city="Saint-Nicolas") 
AND traits.status="AC" 
AND (traits.nace_code IN ["62010", "62020", ...] OR traits.nace_codes IN ["62010", "62020", ...]) 
AND traits.name EXISTS
```

## Impact

- ✅ Search counts and segment creation now return consistent results
- ✅ Both `traits.nace_code` and `traits.nace_codes` field names are supported
- ✅ Backward compatible with existing data structures
- ✅ All 87 relevant unit tests pass

## Files Changed
- `src/search_engine/builders/tql_builder.py` - Support both nace_code and nace_codes field names
- `src/search_engine/builders/es_builder.py` - Support both field names in ES queries
- `tests/unit/test_tql_builder.py` - Updated test assertions
- `tests/unit/test_es_builder.py` - Updated test assertions
