from fastapi import status


def test_admin_requires_api_key(client):
    # Without API key should be unauthorized
    resp = client.get("/admin")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
