import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture(scope="session")
def client():
    """TestClient using an in-memory SQLite DB for isolation."""
    # Import here to ensure app is available on sys.path
    from app.main import app
    from app.db import Base, get_db
    import app.db as app_db

    import tempfile

    tmp = tempfile.NamedTemporaryFile(prefix="test_urls_db_", suffix=".sqlite", delete=False)
    db_path = tmp.name
    tmp.close()

    db_url = f"sqlite:///{db_path}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Replace the module-level engine/session for app.db so all code uses the test DB
    app_db.engine = engine
    app_db.SessionLocal = TestingSessionLocal

    # Create tables
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
