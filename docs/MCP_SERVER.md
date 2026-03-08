# MCP Server for CDP_Merged

Model Context Protocol (MCP) server exposing core PostgreSQL-backed read-only tools for standardized agent access.

## Overview

The MCP server provides a standardized interface for MCP-compatible clients to query the CDP's PostgreSQL database. MCP is an open protocol for integrating external data sources and tools with AI systems. It exposes 7 core read-only tools:

| Tool | Purpose |
|------|---------|
| `search_companies` | Search companies by keywords, city, NACE, status |
| `aggregate_companies` | Analytics aggregation (industry, city, legal form) |
| `get_company_360_profile` | Complete 360° view (KBO + Teamleader + Exact) |
| `get_industry_summary` | Pipeline/revenue by industry |
| `get_geographic_revenue_distribution` | Revenue by city |
| `get_identity_link_quality` | KBO matching coverage |
| `find_high_value_accounts` | Risk/opportunity accounts |

## Quick Start

### Stdio Mode (Default)

```bash
./scripts/start_mcp_server.sh
```

### SSE Mode (HTTP API)

```bash
./scripts/start_mcp_server.sh --sse 8001
```

Health check: http://localhost:8001/health  
SSE endpoint: http://localhost:8001/sse

## Client Configuration

MCP servers can be used with any MCP-compatible client. The stdio transport is the most common for local integration.

Example configuration format (client-dependent):
```json
{
  "mcpServers": {
    "cdp-postgresql": {
      "command": "bash",
      "args": [
        "/home/ff/Documents/CDP_Merged/scripts/start_mcp_server.sh"
      ],
      "env": {
        "DATABASE_URL": "postgresql://cdpadmin:cdpadmin123@localhost:5432/cdp?sslmode=disable"
      }
    }
  }
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | Built from parts | Full PostgreSQL connection string |
| `DB_HOST` | localhost | Database host |
| `DB_NAME` | cdp | Database name |
| `DB_USER` | cdpadmin | Database user |
| `DB_PASSWORD` | cdpadmin123 | Database password |
| `DB_PORT` | 5432 | Database port |
| `DB_SSLMODE` | disable | SSL mode |

## Resources

The server also exposes read-only resources:

- `cdp://schema/companies` - Companies table schema
- `cdp://stats/summary` - Database statistics

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Desktop │────▶│   MCP Server    │────▶│   PostgreSQL    │
│  or MCP Client  │     │  (this server)  │     │    (cdp db)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌─────────────────┐
                        │  Unified360     │
                        │  Query Service  │
                        └─────────────────┘
```

## Implementation Details

- **File**: `src/mcp_server.py`
- **Server**: MCP SDK with stdio or SSE transport
- **Services**: Uses existing `PostgreSQLSearchService` and `Unified360Service`
- **Safety**: Read-only tools, no mutations exposed

## Testing

```bash
# Start server in SSE mode
./scripts/start_mcp_server.sh --sse 8001 &

# Test health
curl http://localhost:8001/health

# Stop server
pkill -f mcp_server
```

## Future Enhancements

- Add write tools with approval flows
- Add streaming responses for large result sets
- Add caching layer for frequent queries
- Add query plan exposition for transparency
