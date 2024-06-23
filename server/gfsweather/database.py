import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URI = os.getenv('DATABASE_URI')

engine = create_engine(DATABASE_URI)
session_maker = sessionmaker(bind=engine)


def get_session():
    with session_maker() as session:
        yield session
