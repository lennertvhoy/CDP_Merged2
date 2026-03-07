#!/usr/bin/env bash
set -euo pipefail

docker exec tracardi_api sh -lc 'python - <<'"'"'PY'"'"'
from pathlib import Path

path = Path("/app/app/api/generic_endpoint.py")
text = path.read_text()

if "query.where.strip() == \"*\"" in text:
    print("generic_endpoint.py already patched")
    raise SystemExit(0)

backup = Path("/app/app/api/generic_endpoint.py.bak_profile_search_wildcard")
if not backup.exists():
    backup.write_text(text)

replacements = [
    (
        "    result = await raw_db.index(index.value).query_by_sql(query.where, start=0, limit=query.limit)\n",
        "    where = \"\" if query.where is not None and query.where.strip() == \"*\" else query.where\n"
        "    result = await raw_db.index(index.value).query_by_sql(where, start=0, limit=query.limit)\n",
    ),
    (
        "async def time_range_with_sql(index: IndexesHistogram, query: DatetimeRangePayload, page: Optional[int] = None):\n"
        "    if page is not None:\n",
        "async def time_range_with_sql(index: IndexesHistogram, query: DatetimeRangePayload, page: Optional[int] = None):\n"
        "    if query.where is not None and query.where.strip() == \"*\":\n"
        "        query.where = \"\"\n"
        "    if page is not None:\n",
    ),
    (
        "async def histogram_with_sql(index: IndexesHistogram, query: DatetimeRangePayload, group_by: str = None):\n\n"
        "    return await raw_db.index(index.value).histogram_by_sql_in_time_range(query, group_by)\n",
        "async def histogram_with_sql(index: IndexesHistogram, query: DatetimeRangePayload, group_by: str = None):\n"
        "    if query.where is not None and query.where.strip() == \"*\":\n"
        "        query.where = \"\"\n\n"
        "    return await raw_db.index(index.value).histogram_by_sql_in_time_range(query, group_by)\n",
    ),
]

updated = text
for old, new in replacements:
    if old not in updated:
        raise SystemExit(f"Expected snippet not found in {path}: {old!r}")
    updated = updated.replace(old, new, 1)

path.write_text(updated)
print("Patched generic_endpoint.py")
PY'

docker restart tracardi_api >/dev/null
sleep 5
docker logs --tail 20 tracardi_api
