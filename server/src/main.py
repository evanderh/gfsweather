#!/usr/bin/env python

import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def index():
    return 'Hello!'

if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host='0.0.0.0',
        reload=True,
    )
