import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

DATABASE_URL = 'postgresql://postgres:postgres@postgis:5432/postgres'

engine = create_engine(DATABASE_URL)
session_maker = sessionmaker(bind=engine)


def get_session():
    with session_maker() as session:
        yield session
