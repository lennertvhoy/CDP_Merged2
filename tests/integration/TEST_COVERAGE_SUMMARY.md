# CDP Chatbot Integration Tests - Coverage Summary

## Overview

This test suite provides comprehensive coverage for the critical user workflow:
**Count → Segment Creation → External Push Alignment**

The recent bug where "count 2394 IT companies" but "segment creation returns 0"
demonstrated the need for these alignment verification tests.

## Test File Location

```
tests/integration/test_count_segment_alignment.py
```

## Test Scenarios (15 Tests)

### Core Alignment Tests (Tests 1-12)

| Test | Scenario | Expected Count | Key Assertion |
|------|----------|----------------|---------------|
| 1 | IT companies in Gent → Create segment | 2394 | search_count == segment_count |
| 2 | Restaurants in Brussels with email | 856 | search_count == segment_count |
| 3 | Juridical form NV companies | 15420 | search_count == segment_count |
| 4 | Active dentists in Brussels | 324 | search_count == segment_count |
| 5 | Multiple criteria (city + NACE + status) | variable | search_count == segment_count |
| 6 | Bakeries in Gent (per user spec) | 138 | search_count == segment_count |
| 7 | Zero results handling | 0 | Empty segment handled gracefully |
| 8 | Large result set pagination | 15234 | No records lost in pagination |
| 9 | Special characters (Sint-Niklaas) | 187 | search_count == segment_count |
| 10 | Spelling variants (Brussel/Brussels) | >0 | Normalization works correctly |
| 11 | Push to Flexmail | 2394 | search == segment == pushed |
| 12 | BV juridical form companies | 28450 | search_count == segment_count |

### Bug Verification Tests (Tests 13+)

| Test | Scenario | Purpose |
|------|----------|---------|
| 13 | Bug reproduction: count N → segment 0 | Verifies test suite catches the original bug |
| 14 | Complex TQL conditions | Edge case: complex OR/AND conditions |
| 15 | Multiple segments from same search | Edge case: segment count consistency |

## Running the Tests

### Run All Integration Tests
```bash
cd /home/ff/.openclaw/workspace/CDP_Merged
source venv/bin/activate
python -m pytest tests/integration/test_count_segment_alignment.py -v
```

### Run with Coverage Report
```bash
python -m pytest tests/integration/test_count_segment_alignment.py --cov=src --cov-report=term-missing
```

### Run Specific Test
```bash
python -m pytest tests/integration/test_count_segment_alignment.py::TestCountSegmentAlignment::test_01_it_companies_gent_count_to_segment_alignment -v
```

### Run with Real Services (INTEGRATION_TESTS=1)
```bash
INTEGRATION_TESTS=1 python -m pytest tests/integration/test_count_segment_alignment.py -v
```

## Test Architecture

### Fixtures

- `mock_tracardi_client`: Simulates proper count→segment alignment
- `mock_buggy_tracardi_client`: Simulates the original bug for verification
- `mock_flexmail_client`: Simulates Flexmail external service

### Test Classes

1. **TestCountSegmentAlignment**: Core 12 test scenarios
2. **TestBugReproduction**: Verifies test suite catches bugs
3. **TestEdgeCases**: Additional edge case coverage

## Key Assertions

Every test asserts:
```python
assert search_count == segment_count, (
    f"CRITICAL BUG: Search returned {search_count} profiles, "
    f"but segment created with only {segment_count} profiles."
)
```

For full pipeline tests (e.g., Flexmail):
```python
assert search_count == segment_count == pushed_count, (
    f"Full pipeline mismatch: search={search_count}, segment={segment_count}, "
    f"flexmail_push={pushed_count}. All counts must align!"
)
```

## Known Issues Documented

### Test 6: Bakeries in Gent (138 expected)
- User specification: ~138 bakeries in Gent
- Test verifies: count matches segment, count equals 138
- If count ≠ 138: Indicates stale data or incorrect NACE code mapping

### Test 13: Bug Reproduction
- Intentionally tests the buggy behavior
- Should catch: search=2394, segment=0
- Confirms test suite would catch the original bug

## Maintenance Notes

### Adding New Tests
1. Add test method to appropriate class
2. Use `mock_tracardi_client` fixture
3. Assert `search_count == segment_count`
4. Add descriptive failure message

### Updating Expected Counts
If actual data counts change:
1. Update the mock in `mock_tracardi_client` fixture
2. Update the assertion in the test
3. Document reason for change

## Future Enhancements

- [ ] Add real integration tests against staging Tracardi
- [ ] Add performance benchmarks for large datasets
- [ ] Add concurrent segment creation tests
- [ ] Add retry logic verification tests
