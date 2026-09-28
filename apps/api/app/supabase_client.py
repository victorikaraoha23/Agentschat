"""Supabase integration boundary for the FastAPI backend (Task 3.1).

One place owns client creation so future application services import from here
instead of reaching for credentials or the Supabase SDK directly. No database
repositories, no business models, no auth flows — only connectivity.

The client always uses the privileged service-role key (server-only), never the
browser anon key. When ``AGENTSCHAT_API_SUPABASE_*`` are absent the client
cannot be created: ``get_supabase_client`` raises ``SupabaseNotConfiguredError``
and the application runs without Supabase rather than pretending a connection
exists. Credentials are never logged — the client is logged only as
configured/unconfigured, never by URL or key material.
"""

from __future__ import annotations

from supabase import Client, create_client

from app.config import Settings


class SupabaseNotConfiguredError(RuntimeError):
    """Raised when Supabase credentials are absent — local development runs without them."""


def is_supabase_configured(settings: Settings) -> bool:
    """Whether ``settings`` carries a complete backend Supabase credential pair."""
    return settings.supabase_configured


def get_supabase_client(settings: Settings) -> Client:
    """Create a backend Supabase client from validated ``settings``.

    Creates a fresh client per call (no caching, no global): the only caller
    today is startup verification, and future services will decide their own
    lifecycle. Raises ``SupabaseNotConfiguredError`` when either value is
    absent — never creates a client with placeholder or partial credentials.
    """
    if settings.supabase_url is None or settings.supabase_service_role_key is None:
        raise SupabaseNotConfiguredError(
            "Supabase is not configured: set AGENTSCHAT_API_SUPABASE_URL and "
            "AGENTSCHAT_API_SUPABASE_SERVICE_ROLE_KEY together, or leave both unset."
        )
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
