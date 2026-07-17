from fastapi import status
from app.config import settings


def test_host_header_not_used_for_short_url(client):
    # Create a URL while spoofing Host header; short_url should use BASE_URL from settings
    headers = {"host": "evil.example"}
    create = client.post("/shorten", json={"long_url": "https://hostsafe.example"}, headers=headers)
    assert create.status_code == status.HTTP_200_OK
    short = create.json()["short_url"]
    assert short.startswith(settings.base_url)
