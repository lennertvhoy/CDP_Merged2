#!/usr/bin/env bash
set -euo pipefail

# Hotfix for Tracardi GUI profile search date range issue
# 
# The GUI sends profile search requests without minDate/maxDate fields,
# but the API defaults both from/to dates to current timestamp, causing:
# "Incorrect time range. From date is earlier than or equal to to date."
#
# This patch modifies the time_range_with_sql and histogram_with_sql functions
# to use a wider default date range (1970 to 2100) when dates are not provided.

# Apply patch via Python script running inside the container
cat > /tmp/patch_gui_dates.py << 'PYEOF'
import sys
sys.path.insert(0, "/app")

from pathlib import Path

path = Path("/app/app/api/generic_endpoint.py")
text = path.read_text()

# Check if already patched
if "query.minDate is None or (query.minDate.absolute is None and query.minDate.delta is None)" in text:
    print("generic_endpoint.py already patched for GUI dates")
    sys.exit(0)

# Create backup
backup = Path("/app/app/api/generic_endpoint.py.bak_gui_dates")
if not backup.exists():
    backup.write_text(text)
    print("Created backup")

# Patch time_range_with_sql
old_code1 = '''async def time_range_with_sql(index: IndexesHistogram, query: DatetimeRangePayload, page: Optional[int] = None):
    if query.where is not None and query.where.strip() == "*":
        query.where = ""
    if page is not None:'''

new_code1 = '''async def time_range_with_sql(index: IndexesHistogram, query: DatetimeRangePayload, page: Optional[int] = None):
    if query.where is not None and query.where.strip() == "*":
        query.where = ""
    # Default date range for GUI requests that dont include dates
    if query.minDate is None or (query.minDate.absolute is None and query.minDate.delta is None):
        from tracardi.domain.time_range_query import DatePayload, DatetimePayload
        query.minDate = DatePayload(absolute=DatetimePayload(year=1970, month=1, date=1, hour=0, minute=0, second=0, meridiem="AM", timeZone=0))
    if query.maxDate is None or (query.maxDate.absolute is None and query.maxDate.delta is None):
        from tracardi.domain.time_range_query import DatePayload, DatetimePayload
        query.maxDate = DatePayload(absolute=DatetimePayload(year=2100, month=12, date=31, hour=11, minute=59, second=59, meridiem="PM", timeZone=0))
    if page is not None:'''

if old_code1 in text:
    text = text.replace(old_code1, new_code1, 1)
    print("Patched time_range_with_sql")
else:
    print("WARNING: Could not find time_range_with_sql to patch")

# Patch histogram_with_sql
old_code2 = '''async def histogram_with_sql(index: IndexesHistogram, query: DatetimeRangePayload, group_by: str = None):
    if query.where is not None and query.where.strip() == "*":
        query.where = ""

    return await raw_db.index(index.value).histogram_by_sql_in_time_range(query, group_by)'''

new_code2 = '''async def histogram_with_sql(index: IndexesHistogram, query: DatetimeRangePayload, group_by: str = None):
    if query.where is not None and query.where.strip() == "*":
        query.where = ""
    # Default date range for GUI requests that dont include dates
    if query.minDate is None or (query.minDate.absolute is None and query.minDate.delta is None):
        from tracardi.domain.time_range_query import DatePayload, DatetimePayload
        query.minDate = DatePayload(absolute=DatetimePayload(year=1970, month=1, date=1, hour=0, minute=0, second=0, meridiem="AM", timeZone=0))
    if query.maxDate is None or (query.maxDate.absolute is None and query.maxDate.delta is None):
        from tracardi.domain.time_range_query import DatePayload, DatetimePayload
        query.maxDate = DatePayload(absolute=DatetimePayload(year=2100, month=12, date=31, hour=11, minute=59, second=59, meridiem="PM", timeZone=0))

    return await raw_db.index(index.value).histogram_by_sql_in_time_range(query, group_by)'''

if old_code2 in text:
    text = text.replace(old_code2, new_code2, 1)
    print("Patched histogram_with_sql")
else:
    print("WARNING: Could not find histogram_with_sql to patch")

path.write_text(text)
print("Patch complete")
PYEOF

docker cp /tmp/patch_gui_dates.py tracardi_api:/tmp/
docker exec tracardi_api python3 /tmp/patch_gui_dates.py

echo "Restarting tracardi_api container..."
docker restart tracardi_api >/dev/null
sleep 5
echo "Container restarted. Recent logs:"
docker logs --tail 10 tracardi_api
