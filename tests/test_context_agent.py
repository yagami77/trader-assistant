from app.config import get_settings


def test_context_disabled(monkeypatch):
    from app.agents.context_agent import get_context_summary

    monkeypatch.setenv("CONTEXT_ENABLED", "false")
    get_settings.cache_clear()
    summary, sources = get_context_summary()
    assert summary == []
    assert sources == []


def test_context_enabled(monkeypatch):
    from app.agents.context_agent import get_context_summary

    def fake_get_context(self):
        return [
            type("C", (), {"title": "Rates", "detail": "Hawkish"})(),
            type("C", (), {"title": "USD", "detail": "Strong"})(),
        ]

    monkeypatch.setenv("CONTEXT_ENABLED", "true")
    monkeypatch.setenv("CONTEXT_API_BASE_URL", "https://example.com")
    get_settings.cache_clear()
    monkeypatch.setattr("app.providers.context_provider.HttpContextProvider.get_context", fake_get_context)
    summary, sources = get_context_summary()
    assert summary
    assert sources == ["context:api"]
