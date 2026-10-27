
from django.core.cache import cache


MAX_FAILED_ATTEMPTS = 5
BLOCK_WINDOW = 300  # 5 minutes


def detect_brute_force(identifier):
    """
    Track failed login attempts for a username/IP combination.
    Returns True when the threshold is exceeded.
    """

    cache_key = f"failed_login:{identifier}"

    attempts = cache.get(cache_key, 0)
    attempts += 1

    cache.set(cache_key, attempts, BLOCK_WINDOW)

    return attempts >= MAX_FAILED_ATTEMPTS