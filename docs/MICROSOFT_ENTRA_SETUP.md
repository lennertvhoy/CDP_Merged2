# Microsoft Entra ID (Azure AD) Authentication Setup

This guide configures the CDP Chatbot to authenticate users with Microsoft work accounts.

## Overview

- **Authentication Method**: OAuth 2.0 / OpenID Connect via Microsoft Entra ID
- **User Experience**: "Sign in with Microsoft" button
- **Security**: Domain-restricted, audit-logged, token-based sessions

## Current Configuration

| Setting | Value | Status |
|---------|-------|--------|
| Tenant ID | `ce408fd5-2526-4cbb-bbe6-f0c2e188b89d` | ✅ Configured |
| Client ID | `d13725b8-ce4e-4103-9518-2d66bcce5beb` | ✅ Configured |
| App Name | "CDP Chatbot" | ✅ Created |
| Local Redirect URI | `http://localhost:8000/auth/oauth/azure-ad/callback` | ✅ Configured |

## Quick Start

### 1. Verify Azure AD App Registration

The app registration has been created in your Azure subscription. Verify it exists:

```bash
az ad app show --id d13725b8-ce4e-4103-9518-2d66bcce5beb
```

### 2. Configure Environment

Edit `.env.local` and enable Azure AD:

```bash
# Enable Microsoft Entra ID authentication
CHAINLIT_ENABLE_AZURE_AD=true

# These are already configured:
AZURE_AD_TENANT_ID=ce408fd5-2526-4cbb-bbe6-f0c2e188b89d
AZURE_AD_CLIENT_ID=d13725b8-ce4e-4103-9518-2d66bcce5beb
AZURE_AD_CLIENT_SECRET=<set-in-.env.local-or-secret-store>
```

Retrieve the secret from the approved secret source only. Do not copy a real client secret from tracked documentation.

### 3. Run Setup Validation

```bash
uv run python scripts/setup_azure_ad_auth.py
```

### 4. Start Application

```bash
docker compose up -d --build
# Or for local development:
uv run python -m uvicorn src.app:chainlit_server_app --host 0.0.0.0 --port 8000
```

### 5. Test Authentication

1. Navigate to `http://localhost:8000`
2. Click "Sign in with Microsoft"
3. Sign in with your work account
4. Verify your profile appears in the UI

## Domain Restrictions (Optional)

To restrict authentication to specific email domains:

```bash
# .env.local
AZURE_AD_ALLOWED_DOMAINS=yourcompany.com,subsidiary.com
```

Users with email addresses outside these domains will be rejected.

## Production Deployment

For production deployment to your server farm:

1. **Update Redirect URIs** in Azure AD:
   - Add: `https://your-domain.com/auth/oauth/azure-ad/callback`
   - Remove or keep localhost for admin access

2. **Rotate Client Secret**:
   ```bash
   az ad app credential reset --id d13725b8-ce4e-4103-9518-2d66bcce5beb
   ```
   Update `.env.production` with the new secret.

3. **Use HTTPS**: Azure AD requires HTTPS in production.

4. **Store Secret Securely**:
   - Use Azure Key Vault or similar
   - Never commit secrets to git

## Troubleshooting

### "Invalid client secret"
- The secret may have expired (default: 1 year)
- Generate a new one: `az ad app credential reset --id <client-id>`

### "Reply URL mismatch"
- The redirect URI in the request doesn't match Azure AD configuration
- Verify in Azure Portal: App Registration > Authentication > Redirect URIs

### "User not allowed"
- Check `AZURE_AD_ALLOWED_DOMAINS` setting
- Verify user is in the allowed domain list

### "Web search not working"
- Web search is disabled by default (`WEB_SEARCH_POLICY=disabled`)
- To enable restricted mode: `WEB_SEARCH_POLICY=restricted`

## Security Considerations

1. **Token Storage**: Chainlit stores OAuth tokens in the session (server-side)
2. **Session Timeout**: 3600 seconds (configurable in `.chainlit/config.toml`)
3. **PII Handling**: User email and object ID are stored in metadata
4. **Audit Logging**: Authentication events are logged

## Architecture

```
┌─────────────┐     OAuth 2.0     ┌─────────────────┐
│   User      │ ────────────────> │  Microsoft      │
│  Browser    │ <──────────────── │  Entra ID       │
└─────────────┘   ID Token +      │  (Azure AD)     │
       │          Access Token    └─────────────────┘
       │                                    │
       │                                    │ Validates
       │                                    │ credentials
       ▼                                    ▼
┌──────────────────────────────────────────────────┐
│           CDP Chatbot (Chainlit)                  │
│  ┌────────────────────────────────────────────┐  │
│  │  OAuth Callback                            │  │
│  │  - Receives user info from Entra ID        │  │
│  │  - Validates domain (optional)             │  │
│  │  - Creates user session                    │  │
│  └────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────┐  │
│  │  PostgreSQL Data Layer                     │  │
│  │  - Stores user profile                     │  │
│  │  - Stores conversation threads             │  │
│  │  - Per-user isolation                      │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## Files Modified

- `.env.local` - Environment variables (updated)
- `.env.example` - Template for new setups (updated)
- `src/config.py` - Configuration schema (updated)
- `src/app.py` - OAuth callback with domain validation (updated)
- `.chainlit/config.toml` - OAuth provider configuration (updated)
- `src/services/web_search_policy.py` - Web search guardrails (new)
- `scripts/setup_azure_ad_auth.py` - Setup helper (new)
- `docs/MICROSOFT_ENTRA_SETUP.md` - This documentation (new)

## Next Steps

1. ✅ Azure AD App Registration created
2. ✅ Configuration files updated
3. ✅ Domain validation implemented
4. ✅ Web search policy framework added
5. 🔄 Test locally with `CHAINLIT_ENABLE_AZURE_AD=true`
6. 🔄 Verify after March 14 when Azure quota resets
7. 🔄 Deploy to production server farm

## References

- [Microsoft Identity Platform Documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/)
- [Chainlit OAuth Configuration](https://docs.chainlit.io/authentication/oauth)
- [Azure AD App Registration Quickstart](https://docs.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
