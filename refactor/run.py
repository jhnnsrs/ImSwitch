#!/usr/bin/env python3
"""
Simple script to run the microscope API.

This script:
1. Imports the action definitions to register them
2. Creates and starts the FastAPI application

Usage:
    python refactor/run.py
    # or
    python -m refactor.run
"""

import uvicorn

# Import actions to register them with the global registry
from refactor.api import actions  # noqa: F401

# Import the app factory
from refactor.api import create_app


def main():
    """Run the microscope API server."""
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
