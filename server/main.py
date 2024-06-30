#!/usr/bin/env python

import os
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

@app.get("/api/forecast_cycle")
def cycle_datetime():
    current_path = os.path.join('layers', 'current')

    if os.path.islink(current_path):
        current_cycle = os.readlink(current_path)
        startDatetime = datetime.strptime(current_cycle, '%Y-%m-%dT%H')
        numForecasts = len(os.listdir(current_path))
        
        return {
            'startDatetime': startDatetime,
            'numForecasts': numForecasts,
        }
    else:
        raise HTTPException(status_code=500, detail="Internal Server Error")

environment = os.getenv('ENV', 'development')
if environment == 'development':
    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://localhost:5173'],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host='0.0.0.0',
        reload=True,
    )
