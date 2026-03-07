#!/usr/bin/env bash
set -euo pipefail

INDEX="${TRACARDI_PROFILE_INDEX:-$(
  curl -fsS 'http://127.0.0.1:9200/_cat/indices?h=index,docs.count&s=index' \
    | grep 'tracardi-profile-' \
    | sort -k2,2nr \
    | awk '$2 > 0 { print $1; exit }'
)}"

if [[ -z "${INDEX}" ]]; then
  echo "Could not determine the active Tracardi profile index." >&2
  exit 1
fi

count_missing_update() {
  curl -fsS -H 'Content-Type: application/json' \
    -d '{"query":{"bool":{"must":[{"exists":{"field":"metadata.time.create"}}],"must_not":[{"exists":{"field":"metadata.time.update"}}]}}}' \
    "http://127.0.0.1:9200/${INDEX}/_count" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["count"])'
}

echo "profile_index=${INDEX}"
echo "missing_update_before=$(count_missing_update)"

curl -fsS -X POST \
  -H 'Content-Type: application/json' \
  "http://127.0.0.1:9200/${INDEX}/_update_by_query?conflicts=proceed&refresh=true" \
  -d '{
    "script": {
      "lang": "painless",
      "source": "if (ctx._source.metadata == null) { ctx._source.metadata = [:]; } if (ctx._source.metadata.time == null) { ctx._source.metadata.time = [:]; } if (ctx._source.metadata.time.update == null) { if (ctx._source.metadata.time.create != null) { ctx._source.metadata.time.update = ctx._source.metadata.time.create; } else if (ctx._source.metadata.time.insert != null) { ctx._source.metadata.time.update = ctx._source.metadata.time.insert; } }"
    },
    "query": {
      "bool": {
        "must": [
          {"exists": {"field": "metadata.time.create"}}
        ],
        "must_not": [
          {"exists": {"field": "metadata.time.update"}}
        ]
      }
    }
  }'

echo
echo "missing_update_after=$(count_missing_update)"
