from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from app.config import settings

# 1. Engine with connection pooling
engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.db_url else {},
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# 2. Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Base for models
Base = declarative_base()

# 4. Per-request dependency - FastAPI me use hoga
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 5. Tables banane ke liye
def init_db():
    Base.metadata.create_all(bind=engine)

    if "sqlite" in settings.db_url:
        with engine.begin() as conn:
            inspector = inspect(conn)
            if inspector.has_table("urls"):
                columns = {col["name"] for col in inspector.get_columns("urls")}

                # Handle legacy schemas that used `long_url` or lacked `original_url`.
                if "long_url" in columns and "original_url" not in columns:
                    conn.execute(text("ALTER TABLE urls RENAME COLUMN long_url TO original_url"))
                    columns = {col["name"] for col in inspector.get_columns("urls")}

                if "original_url" not in columns:
                    try:
                        conn.execute(text("ALTER TABLE urls ADD COLUMN original_url VARCHAR"))
                    except Exception:
                        pass

                if "long_url" not in columns:
                    try:
                        conn.execute(text("ALTER TABLE urls ADD COLUMN long_url VARCHAR"))
                    except Exception:
                        pass

                if "slug" not in columns:
                    try:
                        conn.execute(text("ALTER TABLE urls ADD COLUMN slug VARCHAR"))
                    except Exception:
                        pass

                if "clicks" not in columns:
                    try:
                        conn.execute(text("ALTER TABLE urls ADD COLUMN clicks INTEGER DEFAULT 0"))
                    except Exception:
                        pass

                if "code" not in columns:
                    try:
                        conn.execute(text("ALTER TABLE urls ADD COLUMN code VARCHAR(50)"))
                    except Exception:
                        pass

                if "last_clicked_at" not in columns:
                    try:
                        conn.execute(text("ALTER TABLE urls ADD COLUMN last_clicked_at DATETIME"))
                    except Exception:
                        pass

                if "created_at" not in columns:
                    try:
                        # Add created_at with a default so new rows receive a timestamp
                        conn.execute(text("ALTER TABLE urls ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                    except Exception:
                        pass
