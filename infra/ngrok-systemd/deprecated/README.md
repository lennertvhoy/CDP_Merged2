# Deprecated Chainlit Services

## Status: CHAINLIT IS DEPRECATED - DO NOT USE

The files in this directory are kept for historical reference only.
Chainlit is no longer part of the supported runtime.

### cdp-chatbot.service.deprecated
- **Original purpose**: Ran Chainlit on port 8000
- **Status**: DEPRECATED - Service disabled and file archived
- **Replacement**: Operator Shell (port 3000) + Operator API (port 8170)
- **Date deprecated**: 2026-03-14

### Migration Path
All user-facing chat/UI flows now go through:
- **Frontend**: Operator Shell (Next.js on port 3000)
- **Backend**: Operator API (FastAPI on port 8170)
- **Chat endpoint**: `/api/operator/chat/stream` (POST with SSE streaming)

See the main project README for current architecture.
