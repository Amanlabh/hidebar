#!/bin/bash
# Start Hidebar - automatically handles virtual environment deactivation

cd "$(dirname "$0")"

# Deactivate virtual environment if active
if [ -n "$VIRTUAL_ENV" ]; then
    echo "Deactivating virtual environment..."
    deactivate 2>/dev/null || true
fi

# Use system Python which has tkinter support
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 Hidebar.py

