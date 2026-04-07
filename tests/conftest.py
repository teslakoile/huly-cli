import pytest

from huly_cli.config import AuthCache, HulyConfig


@pytest.fixture
def fake_config():
    return HulyConfig(
        url="https://test.example.com",
        workspace="test-ws",
        email="test@test.com",
        password="testpass",
    )


@pytest.fixture
def fake_auth():
    return AuthCache(
        account_token="tok-acct",
        workspace_token="tok-ws",
        workspace_id="w-test-123",
        workspace_uuid="uuid-test-456",
        email="test@test.com",
        workspace_slug="test-ws",
        account_id="acc-test-789",
        cached_at=1700000000.0,
    )
