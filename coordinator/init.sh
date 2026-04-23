#!/bin/bash
sleep 10
alembic upgrade head
python -m flask run --host=0.0.0.0 --port=5002