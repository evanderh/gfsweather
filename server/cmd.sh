#!/bin/bash

echo $FASTAPI_ENV
if [ ${FASTAPI_ENV} = 'development' ]; then 
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload; 
else
    gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000; 
fi
