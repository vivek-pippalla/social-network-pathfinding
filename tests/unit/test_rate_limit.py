import hashlib

import pytest

from app.core import rate_limit
from app.domain.errors import AppError, RateLimitedError, UnavailableError


class FakeRedis:
    def __init__(self, counts=None, fail=False):
        self.counts = counts if counts is not None else {}
        self.fail = fail
        self.keys = []

    def eval(self, _script, _key_count, key, _window):
        if self.fail:
            raise OSError("redis unavailable")
        self.keys.append(key)
        count = self.counts.get(key, 0) + 1
        self.counts[key] = count
        return [count, 47]


def test_login_rate_limit_has_ip_and_hashed_email_dimensions():
    redis = FakeRedis()
    email = "alice@example.com"
    rate_limit.check_login(redis, "192.0.2.10", email)
    assert redis.keys == [
        "rate:login:ip:192.0.2.10",
        f"rate:login:email:192.0.2.10:{hashlib.sha256(email.encode()).hexdigest()}",
    ]
    assert email not in " ".join(redis.keys)


def test_sixth_login_attempt_is_429_with_retry_after():
    redis = FakeRedis()
    for _ in range(5):
        rate_limit.check_login(redis, "192.0.2.10", "alice@example.com")
    with pytest.raises(RateLimitedError) as error:
        rate_limit.check_login(redis, "192.0.2.10", "alice@example.com")
    assert error.value.status == 429
    assert error.value.headers["Retry-After"] == "47"


@pytest.mark.parametrize(
    "check,limit,key_args",
    [
        (rate_limit.check_registration, 5, ("127.0.0.1",)),
        (rate_limit.check_search, 30, ("127.0.0.1",)),
    ],
)
def test_register_and_search_limits_return_retry_after(check, limit, key_args):
    redis = FakeRedis()
    for _ in range(limit):
        check(redis, *key_args)
    with pytest.raises(RateLimitedError) as error:
        check(redis, *key_args)
    assert error.value.headers["Retry-After"] == "47"


def test_login_and_register_fail_closed_when_redis_is_unavailable():
    with pytest.raises(UnavailableError):
        rate_limit.check_login(FakeRedis(fail=True), "127.0.0.1", "a@example.com")
    with pytest.raises(UnavailableError):
        rate_limit.check_registration(FakeRedis(fail=True), "127.0.0.1")


def test_redis_failure_log_omits_email_and_password(caplog):
    email = "private-person@example.com"
    password = "very-private-password"
    with pytest.raises(UnavailableError):
        rate_limit.check_login(FakeRedis(fail=True), "192.0.2.1", email)
    assert email not in caplog.text
    assert password not in caplog.text


def test_search_rate_limit_fails_open_when_redis_is_unavailable(caplog):
    rate_limit.check_search(FakeRedis(fail=True), "127.0.0.1")
    assert "rate_limit_unavailable" in caplog.text


def test_rate_limit_error_has_stable_code_and_safe_message():
    error = RateLimitedError(12)
    assert error.code == "RATE_LIMITED"
    assert error.headers == {"Retry-After": "12"}
    assert "alice@example.com" not in error.message
