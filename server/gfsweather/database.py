import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import dotenv

environment = os.getenv('ENV', 'development')
if environment == 'production':
    dotenv.load_dotenv('.env.production.local')
else:
    dotenv.load_dotenv('.env.development')
DATABASE_URI = os.getenv('DATABASE_URI')

engine = create_engine(DATABASE_URI)
session_maker = sessionmaker(bind=engine)


def get_session():
    with session_maker() as session:
        yield session
