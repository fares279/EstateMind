import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    # Throttle counters (and chat memory) live in the cache; each test starts fresh.
    cache.clear()
    yield


@pytest.fixture(autouse=True)
def _no_real_stripe(monkeypatch):
    # Tests must never reach Stripe with the developer's keys: an unmocked call goes
    # to a closed local port and fails at once.
    import stripe
    monkeypatch.setattr(stripe, 'api_key', 'sk_test_offline')
    monkeypatch.setattr(stripe, 'api_base', 'http://127.0.0.1:9')
    yield
