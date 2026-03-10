#!/usr/bin/env python3
"""
MCP (Model Context Protocol) Server for CDP_Merged

Exposes core PostgreSQL-backed read-only tools via the Model Context Protocol,
enabling standardized access for MCP-compatible clients (Claude Desktop, etc.)

Usage:
    # Via stdio (for Claude Desktop)
    python src/mcp_server.py

    # Via SSE (for HTTP clients)
    python src/mcp_server.py --transport sse --port 8001

Environment:
    DATABASE_URL or POSTGRES_CONNECTION_STRING
    Or local `.env.local` / `.env` / `.env.database`
    Or: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import cast

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool
from pydantic import AnyUrl

# Import CDP services
from core.database_url import resolve_database_url
from services.postgresql_search import PostgreSQLSearchService
from services.unified_360_queries import Unified360Service

# Server metadata
SERVER_NAME = "cdp-postgresql-query-server"
SERVER_VERSION = "1.0.0"
DEFAULT_SSE_HOST = os.getenv("MCP_SSE_HOST", "127.0.0.1")


def _setup_environment():
    """Set up environment variables for database connection."""
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = resolve_database_url()


@asynccontextmanager
async def app_lifespan(server: Server) -> AsyncIterator[dict]:
    """Manage application lifecycle."""
    # Setup environment
    _setup_environment()

    # Initialize services
    search_service = PostgreSQLSearchService()
    query_360_service = Unified360Service()

    # Ensure connections
    await search_service.ensure_connected()

    yield {
        "search_service": search_service,
        "query_360_service": query_360_service,
    }

    # Cleanup
    await query_360_service.close()


# Initialize MCP server
app = Server(SERVER_NAME, lifespan=app_lifespan)


# ============================================================================
# TOOL DEFINITIONS
# ============================================================================

TOOLS = [
    Tool(
        name="search_companies",
        description="""Search for companies in the PostgreSQL database.

Use this tool for:
- Finding companies by keywords, city, NACE code, or status
- Market sizing questions ("How many restaurants in Brussels?")
- Discovery queries with filters

Parameters support:
- keywords: Search in company names/descriptions
- city: Filter by city name (e.g., "Brussels", "Gent")
- nace_code: Industry classification code
- status: Company status (AC=active, default includes all)
- min_start_date: Filter by founding date
- limit: Max results (default 100, max 1000)
- offset: Pagination offset
""",
        inputSchema={
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "Search keywords for company names/descriptions",
                },
                "city": {
                    "type": "string",
                    "description": "Filter by city name (e.g., 'Brussels', 'Gent', 'Antwerpen')",
                },
                "nace_code": {
                    "type": "string",
                    "description": "NACE industry code (e.g., '56101' for restaurants)",
                },
                "status": {
                    "type": "string",
                    "description": "Company status filter. 'AC' = active only, omit = all statuses",
                },
                "min_start_date": {
                    "type": "string",
                    "description": "Minimum founding date (ISO format: YYYY-MM-DD)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default 100, max 1000)",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 1000,
                },
                "offset": {
                    "type": "integer",
                    "description": "Pagination offset",
                    "default": 0,
                    "minimum": 0,
                },
            },
        },
    ),
    Tool(
        name="aggregate_companies",
        description="""Aggregate company data for analytics.

Use this tool for:
- Industry analysis ("Top industries in Brussels")
- Geographic distribution
- Legal form breakdowns
- Status summaries

Supports grouping by:
- nace_code / industry: Industry classification
- city: Geographic distribution
- legal_form: Company legal structure
- status: Active vs inactive
""",
        inputSchema={
            "type": "object",
            "properties": {
                "group_by": {
                    "type": "string",
                    "description": "Field to group by",
                    "enum": ["nace_code", "industry", "city", "legal_form", "status"],
                },
                "city": {"type": "string", "description": "Optional city filter"},
                "keywords": {"type": "string", "description": "Optional keyword filter"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum groups to return",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["group_by"],
        },
    ),
    Tool(
        name="get_company_360_profile",
        description="""Get a complete 360° profile for a company.

Combines data from:
- KBO (Belgian business registry)
- Teamleader (CRM)
- Exact Online (accounting)

Use for: "Give me a 360° view of company KBO 0123.456.789"
""",
        inputSchema={
            "type": "object",
            "properties": {
                "kbo_number": {
                    "type": "string",
                    "description": "KBO number (format: 0123.456.789 or 0123456789)",
                },
                "company_name": {
                    "type": "string",
                    "description": "Company name (alternative to KBO number)",
                },
            },
        },
    ),
    Tool(
        name="get_industry_summary",
        description="""Get pipeline and revenue summary for an industry.

Use this tool for:
- "What is the total pipeline value for software companies?"
- "Which industries have the most revenue?"
- Industry-level CRM and financial analysis

Returns: Total pipeline value, revenue, company count, deal metrics
""",
        inputSchema={
            "type": "object",
            "properties": {
                "industry": {
                    "type": "string",
                    "description": "Industry name or NACE code (e.g., 'software', '56101')",
                },
                "city": {
                    "type": "string",
                    "description": "Optional city filter (e.g., 'Brussels')",
                },
            },
        },
    ),
    Tool(
        name="get_geographic_revenue_distribution",
        description="""Get revenue distribution by city/geography.

Use this tool for:
- "Show me revenue distribution by city"
- "Which cities have the most revenue?"
- Geographic financial analysis

Returns: Revenue totals by city, company counts, deal values
""",
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum cities to return",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                }
            },
        },
    ),
    Tool(
        name="get_identity_link_quality",
        description="""Get KBO identity matching quality metrics.

Use this tool for:
- "How well are source systems linked to KBO?"
- "What is the KBO match rate?"
- Identity reconciliation monitoring

Returns: Match rates by source system, coverage statistics
""",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="find_high_value_accounts",
        description="""Find high-value accounts with risk or opportunity indicators.

Use this tool for:
- "Which high-value accounts have overdue invoices?"
- "Show me at-risk customers"
- Opportunity identification

Returns: Companies with risk/opportunity flags, financial metrics
""",
        inputSchema={
            "type": "object",
            "properties": {
                "min_revenue": {"type": "number", "description": "Minimum annual revenue filter"},
                "has_overdue_invoices": {
                    "type": "boolean",
                    "description": "Filter for companies with overdue invoices",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                },
            },
        },
    ),
]


# ============================================================================
# TOOL HANDLERS
# ============================================================================


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute a tool call."""
    ctx = app.request_context
    lifespan_ctx = ctx.lifespan_context
    search_service: PostgreSQLSearchService = lifespan_ctx["search_service"]
    query_360_service: Unified360Service = lifespan_ctx["query_360_service"]

    try:
        if name == "search_companies":
            result = await search_service.search_profiles(
                keywords=arguments.get("keywords"),
                city=arguments.get("city"),
                nace_code=arguments.get("nace_code"),
                status=arguments.get("status"),
                min_start_date=arguments.get("min_start_date"),
                limit=arguments.get("limit", 100),
                offset=arguments.get("offset", 0),
            )
            # Convert to dict for JSON serialization
            result_dict = {
                "profiles": [
                    p.model_dump() if hasattr(p, "model_dump") else p
                    for p in result.get("profiles", [])
                ],
                "total_count": result.get("total_count"),
                "offset": result.get("offset"),
                "limit": result.get("limit"),
            }
            return [TextContent(type="text", text=json.dumps(result_dict, indent=2, default=str))]

        elif name == "aggregate_companies":
            result = await search_service.aggregate_profiles(
                group_by=arguments["group_by"],
                city=arguments.get("city"),
                keywords=arguments.get("keywords"),
                limit=arguments.get("limit", 10),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "get_company_360_profile":
            if kbo := arguments.get("kbo_number"):
                result = await query_360_service.get_company_360_profile(kbo_number=kbo)
                if result:
                    result_dict = result.model_dump() if hasattr(result, "model_dump") else result
                else:
                    result_dict = {"error": f"Company not found with KBO: {kbo}"}
            elif company_name := arguments.get("company_name"):
                # First search for the company
                search_result = await search_service.search_profiles(
                    keywords=company_name, limit=1
                )
                profiles = search_result.get("profiles", [])
                if profiles:
                    kbo = (
                        profiles[0].kbo_number
                        if hasattr(profiles[0], "kbo_number")
                        else profiles[0].get("kbo_number")
                    )
                    if kbo:
                        result = await query_360_service.get_company_360_profile(kbo_number=kbo)
                        result_dict = (
                            result.model_dump()
                            if result and hasattr(result, "model_dump")
                            else result
                        )
                    else:
                        result_dict = {"error": "Company found but no KBO number available"}
                else:
                    result_dict = {"error": f"Company not found: {company_name}"}
            else:
                result_dict = {"error": "Please provide either kbo_number or company_name"}
            return [TextContent(type="text", text=json.dumps(result_dict, indent=2, default=str))]

        elif name == "get_industry_summary":
            # Map industry name to NACE prefix if needed
            industry = arguments.get("industry", "")
            nace_prefix = None

            # Handle common industry names
            industry_map = {
                "software": "62",
                "it": "62",
                "restaurant": "561",
                "food": "56",
                "construction": "41",
                "retail": "47",
            }

            if industry.lower() in industry_map:
                nace_prefix = industry_map[industry.lower()]
            elif industry.isdigit():
                nace_prefix = industry
            else:
                # Try as NACE code directly
                nace_prefix = industry[:2] if len(industry) >= 2 else industry

            result = await query_360_service.get_industry_pipeline_summary(
                nace_prefix=nace_prefix,
                city=arguments.get("city"),
            )
            result_payload = [r.model_dump() if hasattr(r, "model_dump") else r for r in result]
            return [
                TextContent(type="text", text=json.dumps(result_payload, indent=2, default=str))
            ]

        elif name == "get_geographic_revenue_distribution":
            result = await query_360_service.get_geographic_distribution(
                min_companies=1,
                limit=arguments.get("limit", 20),
            )
            result_payload = [r.model_dump() if hasattr(r, "model_dump") else r for r in result]
            return [
                TextContent(type="text", text=json.dumps(result_payload, indent=2, default=str))
            ]

        elif name == "get_identity_link_quality":
            # Query the identity_link_quality view directly
            pool = search_service._client.pool
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT
                        source_system,
                        total_records,
                        matched_to_kbo,
                        match_rate_pct,
                        unmatched_records
                    FROM identity_link_quality
                    ORDER BY source_system
                """)
                result = [dict(row) for row in rows]
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        elif name == "find_high_value_accounts":
            # Map parameters to what the service expects
            min_exposure = None
            if arguments.get("min_revenue"):
                min_exposure = Decimal(str(arguments["min_revenue"]))

            account_priority = None
            if arguments.get("has_overdue_invoices"):
                account_priority = "high_risk"

            result = await query_360_service.get_high_value_accounts(
                min_exposure=min_exposure,
                account_priority=account_priority,
                limit=arguments.get("limit", 50),
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

        else:
            return [TextContent(type="text", text=f"Error: Unknown tool: {name}")]

    except Exception as e:
        import traceback

        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        return [TextContent(type="text", text=error_msg)]


# ============================================================================
# RESOURCE DEFINITIONS (Read-only data access)
# ============================================================================

RESOURCES = [
    Resource(
        uri=cast(AnyUrl, "cdp://schema/companies"),
        name="Company Database Schema",
        description="Schema information for the companies table",
        mimeType="application/json",
    ),
    Resource(
        uri=cast(AnyUrl, "cdp://stats/summary"),
        name="Database Summary Statistics",
        description="High-level statistics about the CDP database",
        mimeType="application/json",
    ),
]


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return RESOURCES


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource by URI."""
    ctx = app.request_context
    lifespan_ctx = ctx.lifespan_context
    search_service: PostgreSQLSearchService = lifespan_ctx["search_service"]

    if uri == "cdp://schema/companies":
        schema = {
            "table": "companies",
            "description": "Core company data from KBO (Belgian business registry)",
            "columns": [
                {"name": "id", "type": "UUID", "description": "Primary key"},
                {
                    "name": "kbo_number",
                    "type": "TEXT",
                    "description": "Belgian business registry number",
                },
                {"name": "company_name", "type": "TEXT", "description": "Official company name"},
                {
                    "name": "status",
                    "type": "TEXT",
                    "description": "AC=Active, other values for inactive",
                },
                {
                    "name": "industry_nace_code",
                    "type": "TEXT",
                    "description": "Industry classification",
                },
                {"name": "city", "type": "TEXT", "description": "City name"},
                {"name": "website_url", "type": "TEXT", "description": "Company website"},
                {"name": "created_at", "type": "TIMESTAMP", "description": "Record creation time"},
                {"name": "updated_at", "type": "TIMESTAMP", "description": "Last update time"},
            ],
        }
        return json.dumps(schema, indent=2)

    elif uri == "cdp://stats/summary":
        # Get actual counts from database
        try:
            pool = search_service._client.pool
            async with pool.acquire() as conn:
                total = await conn.fetchval("SELECT COUNT(*) FROM companies")
                with_website = await conn.fetchval(
                    "SELECT COUNT(*) FROM companies WHERE website_url IS NOT NULL AND website_url != ''"
                )
                with_geo = await conn.fetchval(
                    "SELECT COUNT(*) FROM companies WHERE geo_latitude IS NOT NULL"
                )

            stats = {
                "total_companies": total,
                "with_website": with_website,
                "with_geolocation": with_geo,
                "coverage": {
                    "website_pct": round(with_website / total * 100, 2) if total else 0,
                    "geo_pct": round(with_geo / total * 100, 2) if total else 0,
                },
            }
            return json.dumps(stats, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})

    else:
        return json.dumps({"error": f"Unknown resource: {uri}"})


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


async def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(description="CDP MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport mode (stdio for Claude Desktop, sse for HTTP)",
    )
    parser.add_argument("--port", type=int, default=8001, help="Port for SSE transport")
    args = parser.parse_args()

    if args.transport == "stdio":
        # Stdio transport for Claude Desktop
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    else:
        # SSE transport for HTTP clients
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_session(
                request.scope, request.receive, request.send
            ) as streams:
                await app.run(streams[0], streams[1], app.create_initialization_options())

        async def handle_health(request):
            return JSONResponse({"status": "ok", "server": SERVER_NAME, "version": SERVER_VERSION})

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/health", handle_health),
                Route("/sse", handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

        import uvicorn

        config = uvicorn.Config(
            starlette_app,
            host=DEFAULT_SSE_HOST,
            port=args.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        print(f"Starting MCP server on http://{DEFAULT_SSE_HOST}:{args.port}")
        print(f"Health check: http://localhost:{args.port}/health")
        print(f"SSE endpoint: http://localhost:{args.port}/sse")
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
