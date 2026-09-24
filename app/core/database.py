import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Read the database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

# Base class for declarative models
Base = declarative_base()

# Engine and session factory will be initialized on first use
engine = None
SessionLocal = None

def get_engine():
    global engine, SessionLocal
    if engine is None:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is not set")
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine

def get_session_local():
    global SessionLocal
    if SessionLocal is None:
        get_engine()  # This will initialize engine and SessionLocal
    return SessionLocal

# Initialize engine if DATABASE_URL is set (e.g., for application startup)
if DATABASE_URL:
    get_engine()

# Dependency to get DB session
def get_db():
    db = get_session_local()()
    try:
        yield db
    finally:
        db.close()