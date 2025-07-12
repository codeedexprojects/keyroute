#!/bin/bash

# Define the port
PORT=8080

PID=$(lsof -ti tcp:$PORT)

if [ -n "$PID" ]; then
    echo "Port $PORT is in use by PID $PID. Killing..."
    kill -9 $PID
    echo "Process $PID killed."
else
    echo "Port $PORT is free."
fi


source ../py_310_env/bin/activate

echo "Starting server on port $PORT..."
python manage.py runserver 0.0.0.0:$PORT
