from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
import app.db as app_db
import app.models as app_models
from app.main import app


engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_shorten_and_redirect_flow():
    response = client.post("/shorten", json={"long_url": "https://example.com"})

    assert response.status_code == 200
    data = response.json()
    assert data["short_url"].endswith(data["code"])

    redirect_response = client.get(f"/{data['code']}", follow_redirects=False)
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"].rstrip("/") == "https://example.com"


def test_admin_access():
    from app.config import settings
    headers = {"X-API-Key": settings.admin_api_key} if settings.admin_api_key else {}
    response = client.get("/admin", headers=headers)
    assert response.status_code == 200


def test_code_analytics_endpoint():
    create_response = client.post("/shorten", json={"long_url": "https://example.com"})
    assert create_response.status_code == 200
    data = create_response.json()
    code = data["code"]

    redirect_response = client.get(f"/{code}", follow_redirects=False)
    assert redirect_response.status_code == 307
    assert redirect_response.headers["location"].rstrip("/") == "https://example.com"

    analytics_response = client.get(f"/api/v1/analytics/{code}")
    assert analytics_response.status_code == 200
    analytics_data = analytics_response.json()
    assert analytics_data["short_code"] == code
    assert analytics_data["total_clicks"] == 1
    assert analytics_data["unique_visitors"] == 1


def test_analytics_stats_endpoint():
    create_response = client.post("/shorten", json={"long_url": "https://example.org"})
    assert create_response.status_code == 200

    stats_response = client.get("/api/v1/analytics/stats")
    assert stats_response.status_code == 200
    stats_data = stats_response.json()
    assert stats_data["total_urls"] >= 1
    assert "total_clicks" in stats_data


def test_init_db_adds_missing_long_url_column_for_legacy_sqlite_table(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy_urls.sqlite"
    db_url = f"sqlite:///{db_path}"
    legacy_engine = create_engine(db_url, connect_args={"check_same_thread": False})

    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE urls (
                    id INTEGER PRIMARY KEY,
                    original_url VARCHAR,
                    slug VARCHAR UNIQUE,
                    created_at DATETIME,
                    clicks INTEGER DEFAULT 0,
                    code VARCHAR(50),
                    last_clicked_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text("INSERT INTO urls (original_url, slug, code) VALUES (:url, :slug, :slug)"),
            {"url": "https://legacy.example", "slug": "legacy123"},
        )

    monkeypatch.setattr(app_db, "engine", legacy_engine)
    monkeypatch.setattr(app_db, "SessionLocal", sessionmaker(autocommit=False, autoflush=False, bind=legacy_engine))
    monkeypatch.setattr(app_db.settings, "db_url", db_url)

    app_db.init_db()

    with legacy_engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info('urls')"))}

    assert "long_url" in columns
    assert "original_url" in columns

    with app_db.SessionLocal() as session:
        session.add(app_models.Url(original_url="https://fresh.example", slug="fresh456", code="fresh456"))
        session.commit()
