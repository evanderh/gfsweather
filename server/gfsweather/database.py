import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')

engine = create_engine(DATABASE_URL)
session_maker = sessionmaker(bind=engine)


def get_session():
    with session_maker() as session:
        yield session
