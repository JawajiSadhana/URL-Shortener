from fastapi import status


def test_shorten_valid(client):
    resp = client.post("/shorten", json={"long_url": "https://example.com"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "code" in data and "short_url" in data


def test_shorten_invalid_scheme(client):
    resp = client.post("/shorten", json={"long_url": "ftp://example.com"})
    # Pydantic `HttpUrl` will reject non-http schemes with 422
    assert resp.status_code == 422


def test_shorten_ssrf_blocked(client):
    # localhost/private addresses should be blocked
    resp = client.post("/shorten", json={"long_url": "http://127.0.0.1/"})
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
