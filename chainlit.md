# CDP AI Assistant

Belgian customer intelligence with a PostgreSQL-first query plane and Tracardi as the downstream activation runtime.

## Choose a Working Mode

- **Marketing Manager**: plan segments, campaign-ready lists, and activation handoff
- **Sales Rep**: find reachable Belgian accounts and qualify fast
- **Data Analyst**: inspect counts, coverage gaps, and market structure
- **Platform Admin**: verify query-plane health, enrichment progress, and safe operational follow-up

## What You Can Ask

- `How many construction companies in Belgium have both email and website data?`
- `Find software companies in Gent with a website and email address`
- `Preview a segment of HR consultancies in Vlaams-Brabant before activation`
- `Compare enrichment readiness across Antwerpen, Brussel, and Liège`
- `Summarize the current query plane, activation runtime, and enrichment monitor status`

## Operating Model

1. Ask in natural language.
2. The assistant translates the request into deterministic retrieval and tool calls.
3. Authoritative search, counts, and analytics come from PostgreSQL-backed services.
4. Segment projection and outbound workflows stay downstream in Tracardi and delivery tools.

## Belgian Data Conventions

- KBO numbers: `XXXX.XXX.XXX`
- VAT numbers: `BE0XXX.XXX.XXX`
- Regions: Vlaanderen, Bruxelles-Capitale, Wallonie

## Providers

- Azure OpenAI
- OpenAI
- Ollama

See `README.md` for environment setup and the wider platform context.
