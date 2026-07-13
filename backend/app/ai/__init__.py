"""AI provider factory: real Gemini, or a deterministic offline fake."""
from ..config import get_settings
from .base import AIProvider


def get_provider(byok_key: str | None = None) -> AIProvider:
    settings = get_settings()
    if byok_key:
        from .gemini import GeminiProvider

        return GeminiProvider(api_key=byok_key)
    if settings.ai_enabled:
        from .gemini import GeminiProvider

        # Vertex mode wins for server traffic: service-account auth and
        # pay-as-you-go quotas instead of the key's free-tier daily cap.
        if settings.gemini_use_vertex:
            return GeminiProvider(api_key=None)
        return GeminiProvider(api_key=settings.gemini_api_key)
    from .fake import FakeProvider

    return FakeProvider()
