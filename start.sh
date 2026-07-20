#!/bin/bash
echo "Building product database (force rebuild)..."
python3 build_db.py
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
