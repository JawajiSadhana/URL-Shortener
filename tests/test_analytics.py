from fastapi import status


def test_analytics_clicks_and_stats(client):
    create = client.post("/shorten", json={"long_url": "https://analytics.example"})
    assert create.status_code == status.HTTP_200_OK
    code = create.json()["code"]

    # Trigger a redirect (this also logs the click)
    r = client.get(f"/{code}", follow_redirects=False)
    assert r.status_code in (status.HTTP_307_TEMPORARY_REDIRECT, status.HTTP_302_FOUND)

    # Check code analytics
    analytics = client.get(f"/api/v1/analytics/{code}")
    assert analytics.status_code == status.HTTP_200_OK
    a = analytics.json()
    assert a["short_code"] == code
    assert a["total_clicks"] >= 1

    # Check stats endpoint
    stats = client.get("/api/v1/analytics/stats")
    assert stats.status_code == status.HTTP_200_OK
    s = stats.json()
    assert "total_urls" in s and "total_clicks" in s
