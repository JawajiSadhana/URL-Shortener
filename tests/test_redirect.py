from fastapi import status


def test_redirect_success(client):
    create = client.post("/shorten", json={"long_url": "https://example.org"})
    assert create.status_code == status.HTTP_200_OK
    code = create.json()["code"]

    redirect = client.get(f"/{code}", follow_redirects=False)
    assert redirect.status_code in (status.HTTP_307_TEMPORARY_REDIRECT, status.HTTP_302_FOUND)
    assert "location" in redirect.headers


def test_redirect_not_found(client):
    resp = client.get("/doesnotexist", follow_redirects=False)
    assert resp.status_code == status.HTTP_404_NOT_FOUND
