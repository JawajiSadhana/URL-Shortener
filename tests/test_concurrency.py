from concurrent.futures import ThreadPoolExecutor


def _create_short(client):
    r = client.post("/shorten", json={"long_url": "https://concurrent.example"})
    return r.status_code, r.json().get("code") if r.status_code == 200 else None


def test_concurrent_shorten_requests_create_unique_codes(client):
    calls = 10
    codes = []
    statuses = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(_create_short, client) for _ in range(calls)]
        for f in futures:
            status, code = f.result()
            statuses.append(status)
            if code:
                codes.append(code)

    assert all(s == 200 for s in statuses)
    assert len(codes) == calls
    assert len(set(codes)) == calls
