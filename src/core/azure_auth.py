"""Shared Azure authentication resolution with MI/KV-first strategy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AzureServiceAuth:
    """Resolved auth material for an Azure service client path."""

    api_key: str | None
    token_credential: Any | None
    token_provider: Callable[[], str] | None
    auth_source: str


class AzureCredentialResolver:
    """Resolve Azure service auth with MI/KV-first and safe fallback behavior."""

    def __init__(self, service_name: str):
        self.service_name = service_name

    def _create_default_credential(self) -> Any:
        from azure.identity import DefaultAzureCredential

        return DefaultAzureCredential()

    def _build_bearer_token_provider(self, credential: Any, scope: str) -> Callable[[], str]:
        from azure.identity import get_bearer_token_provider

        return get_bearer_token_provider(credential, scope)

    def _resolve_secret(self, credential: Any, secret_name: str) -> str:
        from azure.keyvault.secrets import SecretClient

        if not settings.AZURE_KEY_VAULT_URL:
            raise ValueError("AZURE_KEY_VAULT_URL is required for Key Vault secret resolution")
        client = SecretClient(vault_url=settings.AZURE_KEY_VAULT_URL, credential=credential)
        secret = client.get_secret(secret_name).value
        if secret is None:
            raise ValueError(f"Secret {secret_name} has no value in Key Vault")
        return secret

    def resolve(
        self,
        *,
        explicit_key: str | None,
        key_vault_secret_name: str | None,
        token_scope: str,
        require_token_credential: bool,
    ) -> AzureServiceAuth:
        strict = settings.AZURE_AUTH_STRICT_MI_KV_ONLY
        use_default_credential = settings.AZURE_AUTH_USE_DEFAULT_CREDENTIAL
        allow_key_fallback = settings.AZURE_AUTH_ALLOW_KEY_FALLBACK and not strict

        if strict and not use_default_credential:
            raise ValueError(
                f"{self.service_name} strict mode requires AZURE_AUTH_USE_DEFAULT_CREDENTIAL=true"
            )

        token_credential = None
        if use_default_credential:
            try:
                token_credential = self._create_default_credential()
                logger.info(
                    "azure_auth_default_credential_enabled",
                    service=self.service_name,
                )
            except (ImportError, ValueError) as exc:
                if strict:
                    raise ValueError(
                        f"{self.service_name} strict mode failed to initialize DefaultAzureCredential"
                    ) from exc
                logger.warning(
                    "azure_auth_default_credential_unavailable",
                    service=self.service_name,
                    error=str(exc),
                )

        if token_credential is not None:
            try:
                token_provider = self._build_bearer_token_provider(token_credential, token_scope)
                logger.info("azure_auth_using_managed_identity", service=self.service_name)
                return AzureServiceAuth(
                    api_key=None,
                    token_credential=token_credential,
                    token_provider=token_provider,
                    auth_source="managed_identity",
                )
            except (TypeError, ValueError) as exc:
                if strict or require_token_credential:
                    raise ValueError(
                        f"{self.service_name} failed to build token provider from DefaultAzureCredential"
                    ) from exc
                logger.warning(
                    "azure_auth_token_provider_failed",
                    service=self.service_name,
                    error=str(exc),
                )

        if key_vault_secret_name:
            if not settings.AZURE_KEY_VAULT_URL:
                msg = f"{self.service_name} Key Vault secret configured but AZURE_KEY_VAULT_URL is missing"
                if strict:
                    raise ValueError(msg)
                logger.warning("azure_auth_key_vault_url_missing", service=self.service_name)
            elif token_credential is None:
                msg = f"{self.service_name} Key Vault secret configured but no DefaultAzureCredential available"
                if strict:
                    raise ValueError(msg)
                logger.warning(
                    "azure_auth_key_vault_credential_missing",
                    service=self.service_name,
                )
            else:
                try:
                    secret_value = self._resolve_secret(token_credential, key_vault_secret_name)
                    if secret_value:
                        logger.info(
                            "azure_auth_resolved_key_vault_secret",
                            service=self.service_name,
                            secret_name=key_vault_secret_name,
                        )
                        return AzureServiceAuth(
                            api_key=secret_value,
                            token_credential=token_credential,
                            token_provider=None,
                            auth_source="key_vault_secret",
                        )
                except (ImportError, ValueError, RuntimeError) as exc:
                    if strict:
                        raise ValueError(
                            f"{self.service_name} strict mode failed Key Vault secret resolution"
                        ) from exc
                    logger.warning(
                        "azure_auth_key_vault_secret_resolution_failed",
                        service=self.service_name,
                        secret_name=key_vault_secret_name,
                        error=str(exc),
                    )

        if explicit_key and allow_key_fallback:
            logger.info("azure_auth_using_explicit_key_fallback", service=self.service_name)
            return AzureServiceAuth(
                api_key=explicit_key,
                token_credential=None,
                token_provider=None,
                auth_source="explicit_key",
            )

        msg = (
            f"{self.service_name} authentication could not be resolved "
            "(no managed identity token provider, no Key Vault secret, and no allowed key fallback)"
        )
        if strict:
            raise ValueError(msg)

        logger.warning("azure_auth_unresolved", service=self.service_name)
        return AzureServiceAuth(
            api_key=None,
            token_credential=token_credential,
            token_provider=None,
            auth_source="unresolved",
        )
