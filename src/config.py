"""
Unified configuration for CDP_Merged - Tracardi-based CDP with AI chatbot.
Merges CDPT's working Tracardi integration with CDP's multi-LLM support.
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Configuration.
    Supports Ollama (local), OpenAI, and Azure OpenAI.
    """

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ==========================================
    # LLM Provider Configuration (from CDP)
    # ==========================================
    LLM_PROVIDER: str = Field(
        default="openai", description="LLM provider: ollama, openai, azure_openai, moonshot, mock"
    )
    LLM_MODEL: str = Field(
        default="gpt-4o-mini", description="Model name for the selected provider"
    )

    # OpenAI Settings
    OPENAI_API_KEY: str | None = Field(default=None, description="API Key for OpenAI")
    OPENAI_BASE_URL: str | None = Field(default=None, description="Base URL for OpenAI API")

    # Moonshot AI (Kimi) Settings
    MOONSHOT_API_KEY: str | None = Field(default=None, description="API Key for Moonshot AI (Kimi)")
    MOONSHOT_BASE_URL: str = Field(
        default="https://api.moonshot.cn/v1", description="Base URL for Moonshot AI API"
    )

    # Ollama Settings (local development)
    OLLAMA_BASE_URL: str = Field(default="http://127.0.0.1:11434", description="Ollama server URL")

    # Azure OpenAI Settings
    AZURE_OPENAI_API_KEY: str | None = Field(default=None, description="Azure OpenAI API key")
    AZURE_OPENAI_ENDPOINT: str | None = Field(
        default=None, description="Azure OpenAI endpoint URL"
    )
    AZURE_OPENAI_DEPLOYMENT_NAME: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AZURE_OPENAI_DEPLOYMENT_NAME",
            "AZURE_OPENAI_DEPLOYMENT",
        ),
        description="Azure OpenAI deployment name",
    )
    AZURE_OPENAI_API_VERSION: str = Field(
        default="2024-02-01", description="Azure OpenAI API version"
    )
    AZURE_OPENAI_TIMEOUT: float = Field(
        default=30.0, description="Timeout for Azure OpenAI API calls in seconds"
    )
    AZURE_OPENAI_MAX_RETRIES: int = Field(
        default=3, description="Max retries for Azure OpenAI API calls"
    )
    AZURE_OPENAI_MAX_TOKENS: int = Field(
        default=800,
        description="Maximum completion tokens for Azure OpenAI chat responses",
    )
    AZURE_OPENAI_API_KEY_SECRET_NAME: str | None = Field(
        default=None,
        description="Key Vault secret name for Azure OpenAI API key",
    )

    # ==========================================
    # Tracardi CDP (from CDPT - working)
    # ==========================================
    TRACARDI_API_URL: str = Field(
        default="http://localhost:8686", description="Base URL for Tracardi API"
    )
    TRACARDI_API_KEY: str | None = Field(default=None, description="API Key for Tracardi")
    TRACARDI_SOURCE_ID: str = Field(
        default="kbo-source", description="Event Source ID for Tracardi"
    )
    TRACARDI_USERNAME: str = Field(default="", description="Username for Tracardi")
    TRACARDI_PASSWORD: str = Field(default="", description="Password for Tracardi")

    # ==========================================
    # Flexmail Integration (from CDPT - working)
    # ==========================================
    FLEXMAIL_ENABLED: bool = Field(default=False, description="Enable Flexmail integration")
    FLEXMAIL_API_URL: str = Field(
        default="http://localhost:8080/flexmail", description="Base URL for Flexmail API"
    )
    FLEXMAIL_ACCOUNT_ID: str | None = Field(
        default=None, description="Account ID for Flexmail Basic Auth"
    )
    FLEXMAIL_API_TOKEN: str | None = Field(default=None, description="API Token for Flexmail")
    FLEXMAIL_SOURCE_ID: int = Field(default=0, description="Source ID for Flexmail")
    FLEXMAIL_WEBHOOK_SECRET: str | None = Field(
        default=None, description="Shared secret for validating Flexmail webhooks"
    )

    # ==========================================
    # Resend Integration (NEW - alongside Flexmail)
    # ==========================================
    RESEND_API_KEY: str = Field(default="", description="Resend API key")
    RESEND_FROM_EMAIL: str = Field(
        default="onboarding@resend.dev", description="Default sender email for Resend"
    )

    # ==========================================
    # Elasticsearch (from CDPT)
    # ==========================================
    ELASTICSEARCH_URL: str = Field(
        default="http://localhost:9200", description="URL for Elasticsearch instance"
    )

    # ==========================================
    # Application Settings (from CDP)
    # ==========================================
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    CHAINLIT_PORT: int = Field(default=8000, description="Port for Chainlit UI")
    CHAINLIT_DEV_AUTH_ENABLED: bool = Field(
        default=False,
        description="Enable local-only password auth for authenticated Chainlit verification before Entra rollout",
    )
    CHAINLIT_DEV_AUTH_PASSWORD: str | None = Field(
        default=None,
        description="Shared local-only password for Chainlit dev auth; any non-empty username may use it",
    )

    # ==========================================
    # Microsoft Entra ID (Azure AD) OAuth
    # ==========================================
    CHAINLIT_ENABLE_AZURE_AD: bool = Field(
        default=False,
        description="Enable Microsoft Entra ID (Azure AD) OAuth for work account authentication",
    )
    AZURE_AD_TENANT_ID: str | None = Field(
        default=None,
        description="Azure AD Tenant ID for Microsoft work account authentication",
    )
    AZURE_AD_CLIENT_ID: str | None = Field(
        default=None,
        description="Azure AD Application (Client) ID for OAuth",
    )
    AZURE_AD_CLIENT_SECRET: str | None = Field(
        default=None,
        description="Azure AD Client Secret for OAuth",
    )
    AZURE_AD_REDIRECT_URI: str = Field(
        default="http://localhost:8000/auth/oauth/azure-ad/callback",
        description="OAuth redirect URI (must match Azure AD app registration)",
    )
    AZURE_AD_ALLOWED_DOMAINS: str | None = Field(
        default=None,
        description="Comma-separated list of allowed email domains for authentication (e.g., 'company.com,subsidiary.com')",
    )

    # ==========================================
    # Web Search Policy & Controls
    # ==========================================
    WEB_SEARCH_POLICY: str = Field(
        default="disabled",
        description="Web search policy: disabled, restricted (admin-controlled), opt-in, default-on",
    )
    WEB_SEARCH_ALLOWED_DOMAINS: str | None = Field(
        default=None,
        description="Comma-separated list of allowed domains for web search (restricted mode)",
    )
    WEB_SEARCH_BLOCKED_PATTERNS: str | None = Field(
        default=None,
        description="Comma-separated regex patterns to block from web search queries (PII protection)",
    )
    WEB_SEARCH_AUDIT_LOG: bool = Field(
        default=True,
        description="Enable audit logging for web search queries",
    )

    # Feature Flags (from CDP)
    ENABLE_QUERY_VALIDATION: bool = Field(
        default=True, description="Enable query validation and critic layer"
    )
    ENABLE_GDPR_COMPLIANCE: bool = Field(default=True, description="Enable GDPR compliance checks")

    # ==========================================
    # Retrieval Feature Flags (P3/P4)
    # ==========================================
    ENABLE_AZURE_SEARCH_RETRIEVAL: bool = Field(
        default=False,
        description="Switch primary retrieval from Tracardi/TQL to Azure AI Search",
    )
    ENABLE_AZURE_SEARCH_SHADOW_MODE: bool = Field(
        default=False,
        description="Run Azure AI Search in parallel for comparison while keeping Tracardi response",
    )
    ENABLE_CITATION_REQUIRED: bool = Field(
        default=False,
        description="Require citations in grounded responses when Azure retrieval is active",
    )

    # ==========================================
    # Azure AI Search Settings (P3/P4)
    # ==========================================
    AZURE_SEARCH_ENDPOINT: str | None = Field(
        default=None,
        description="Azure AI Search endpoint, e.g. https://<service>.search.windows.net",
    )
    AZURE_SEARCH_API_KEY: str | None = Field(
        default=None, description="Azure AI Search admin/query key"
    )
    AZURE_SEARCH_API_KEY_SECRET_NAME: str | None = Field(
        default=None,
        description="Key Vault secret name for Azure AI Search API key",
    )
    AZURE_SEARCH_INDEX_NAME: str | None = Field(
        default=None, description="Azure AI Search index name"
    )
    AZURE_SEARCH_API_VERSION: str = Field(
        default="2023-11-01", description="Azure AI Search REST API version"
    )
    AZURE_SEARCH_TOP_K: int = Field(
        default=20, description="Max documents retrieved per Azure Search call"
    )
    AZURE_SEARCH_TIMEOUT_SECONDS: float = Field(
        default=10.0, description="Timeout for Azure AI Search calls in seconds"
    )
    AZURE_SEARCH_ID_FIELD: str = Field(
        default="id", description="Document id field in Azure index"
    )
    AZURE_SEARCH_TITLE_FIELD: str = Field(
        default="name", description="Primary title/name field in Azure index"
    )
    AZURE_SEARCH_CONTENT_FIELD: str = Field(
        default="content", description="Primary content/snippet field in Azure index"
    )
    AZURE_SEARCH_URL_FIELD: str = Field(
        default="source_url", description="Source URL field in Azure index"
    )

    # ==========================================
    # Azure Auth Hardening (P6)
    # ==========================================
    AZURE_AUTH_USE_DEFAULT_CREDENTIAL: bool = Field(
        default=True,
        description="Prefer DefaultAzureCredential (Managed Identity / Azure identity chain) for Azure services",
    )
    AZURE_AUTH_ALLOW_KEY_FALLBACK: bool = Field(
        default=True,
        description="Allow explicit API key fallback when MI/KV resolution is unavailable",
    )
    AZURE_AUTH_STRICT_MI_KV_ONLY: bool = Field(
        default=False,
        description="Fail fast unless auth succeeds via Managed Identity and/or Key Vault secret resolution",
    )
    AZURE_KEY_VAULT_URL: str | None = Field(
        default=None,
        description="Key Vault URL used to resolve secret references, e.g. https://<vault>.vault.azure.net",
    )

    # ==========================================
    # PostgreSQL Database Configuration
    # ==========================================
    DATABASE_URL: str | None = Field(
        default=None,
        description="PostgreSQL connection URL (e.g., postgresql://user:pass@host:5432/db?sslmode=require)",
    )
    POSTGRES_CONNECTION_STRING: str | None = Field(
        default=None,
        description="Alternative PostgreSQL connection string (fallback to DATABASE_URL)",
    )


# Global settings instance
settings = Settings()
