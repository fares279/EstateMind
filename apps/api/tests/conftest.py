import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_cache():
    # Throttle counters (and chat memory) live in the cache; each test starts fresh.
    cache.clear()
    yield
