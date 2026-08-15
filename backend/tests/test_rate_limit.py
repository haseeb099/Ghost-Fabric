from app.rate_limit import FixedWindowRateLimiter


def test_rate_limit_is_per_credential_and_resets_each_second() -> None:
    limiter = FixedWindowRateLimiter(limit=2)

    assert limiter.allow("customer-a", now=10.1) == (True, 1)
    assert limiter.allow("customer-a", now=10.2) == (True, 0)
    assert limiter.allow("customer-a", now=10.3) == (False, 0)
    assert limiter.allow("customer-b", now=10.3) == (True, 1)
    assert limiter.allow("customer-a", now=11.0) == (True, 1)
