#!/usr/bin/env python3
"""
Setup script for Microsoft Entra ID (Azure AD) authentication.

This script helps configure the CDP Chatbot to use Microsoft work accounts
for authentication. It validates the configuration and provides next steps.

Usage:
    poetry run python scripts/setup_azure_ad_auth.py

Environment Variables Required:
    AZURE_AD_TENANT_ID: Your Azure AD tenant ID
    AZURE_AD_CLIENT_ID: Your Azure AD app registration client ID  
    AZURE_AD_CLIENT_SECRET: Your Azure AD app registration client secret
"""

import os
import sys
from pathlib import Path

# Add repo root to path
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.config import settings


def check_environment():
    """Check if required environment variables are set."""
    print("=" * 60)
    print("Microsoft Entra ID (Azure AD) Authentication Setup")
    print("=" * 60)
    
    required_vars = [
        "AZURE_AD_TENANT_ID",
        "AZURE_AD_CLIENT_ID", 
        "AZURE_AD_CLIENT_SECRET",
    ]
    
    optional_vars = [
        "AZURE_AD_REDIRECT_URI",
        "AZURE_AD_ALLOWED_DOMAINS",
        "CHAINLIT_ENABLE_AZURE_AD",
    ]
    
    print("\n📋 Required Configuration:")
    print("-" * 40)
    all_required_set = True
    for var in required_vars:
        value = getattr(settings, var, None)
        status = "✅ Set" if value else "❌ Missing"
        print(f"  {var}: {status}")
        if value:
            display_value = "<redacted>" if "SECRET" in var else value
            print(f"    Value: {display_value}")
        else:
            all_required_set = False
    
    print("\n📋 Optional Configuration:")
    print("-" * 40)
    for var in optional_vars:
        value = getattr(settings, var, None)
        status = "✅ Set" if value else "⚪ Not set (using default)"
        print(f"  {var}: {status}")
        if value:
            print(f"    Value: {value}")
    
    return all_required_set


def print_setup_instructions():
    """Print setup instructions for Azure AD."""
    print("\n" + "=" * 60)
    print("🔧 Setup Instructions")
    print("=" * 60)
    
    print("""
1. Azure Portal Configuration:
   - Go to: https://portal.azure.com
   - Navigate to: Azure Active Directory > App registrations
   - Your app: "CDP Chatbot" (d13725b8-ce4e-4103-9518-2d66bcce5beb)

2. Verify Redirect URIs:
   - Authentication > Web > Redirect URIs
   - Add: http://localhost:8000/auth/oauth/azure-ad/callback (for local dev)
   - Add: https://your-domain.com/auth/oauth/azure-ad/callback (for production)

3. Verify API Permissions:
   - API permissions > Microsoft Graph
   - Required: openid, profile, email, User.Read

4. Environment Configuration:
   Edit your .env.local file and set:
   
   CHAINLIT_ENABLE_AZURE_AD=true
   AZURE_AD_TENANT_ID=ce408fd5-2526-4cbb-bbe6-f0c2e188b89d
   AZURE_AD_CLIENT_ID=d13725b8-ce4e-4103-9518-2d66bcce5beb
   AZURE_AD_CLIENT_SECRET=<your-secret-from-step-5>
   
   Optional - restrict to specific domains:
   AZURE_AD_ALLOWED_DOMAINS=yourcompany.com,subsidiary.com

5. Client Secret (if you need a new one):
   - Certificates & secrets > New client secret
   - Copy the secret value immediately (it won't be shown again)
   - Or run: az ad app credential reset --id d13725b8-ce4e-4103-9518-2d66bcce5beb

6. Start the application:
   poetry run python -m uvicorn src.app:chainlit_server_app --host 0.0.0.0 --port 8000

7. Test authentication:
   - Navigate to: http://localhost:8000
   - Click "Sign in with Microsoft"
   - Sign in with your work account
""")


def print_security_notes():
    """Print security recommendations."""
    print("\n" + "=" * 60)
    print("🔒 Security Notes")
    print("=" * 60)
    print("""
- Client Secret: Store securely (Azure Key Vault for production)
- Allowed Domains: Restrict to your organization's domain(s)
- HTTPS: Always use HTTPS in production (Azure AD requires it)
- Token Validation: Chainlit handles token validation automatically
- Session Timeout: Configured in .chainlit/config.toml (default: 3600s)

Current tenant allows any user in the tenant to authenticate.
To restrict to specific domains, set AZURE_AD_ALLOWED_DOMAINS.
""")


def main():
    """Main setup function."""
    if check_environment():
        print("\n✅ All required configuration is set!")
        print(f"\nAzure AD Auth is: {'ENABLED' if settings.CHAINLIT_ENABLE_AZURE_AD else 'DISABLED'}")
        
        if settings.CHAINLIT_ENABLE_AZURE_AD:
            print("\n🚀 To start the application with Azure AD auth:")
            print("   poetry run python -m uvicorn src.app:chainlit_server_app --host 0.0.0.0 --port 8000")
    else:
        print("\n⚠️  Some required configuration is missing.")
        print_setup_instructions()
    
    print_security_notes()


if __name__ == "__main__":
    main()
