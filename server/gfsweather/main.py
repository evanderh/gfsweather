#!/usr/bin/env python

import os
import dotenv
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

environment = os.getenv('ENV', 'development')
if environment == 'production':
    dotenv.load_dotenv('.env.production.local')
else:
    dotenv.load_dotenv('.env.development')

app = FastAPI()
from routes import router

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost',
        'http://localhost:5173'
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

app.include_router(router)

if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host='0.0.0.0',
        reload=True,
    )
