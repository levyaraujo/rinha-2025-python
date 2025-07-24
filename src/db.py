import os
from sqlalchemy import Column, DateTime, Float, String, create_engine, MetaData, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://pyrinha:pyrinha@db:5432/pyrinha"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

metadata = MetaData()

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db_session():
    db = SessionLocal()
    try:    
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class Payment(Base):
    __tablename__ = "payments"

    correlationId = Column("correlationId", UUID, index=True, primary_key=True)
    processor = Column(String)
    amount = Column(Float)
    requestedAt = Column("requestedAt", DateTime)