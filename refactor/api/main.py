#!/usr/bin/env python3
"""
Entrypoint for the Experiment Processing API.

Run with: python -m refactor.api.main
Or: python refactor/api/main.py
"""

import uvicorn

from .app import create_app


def main(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """
    Run the experiment processing API server.

    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload for development
    """
    app = create_app()
    uvicorn.run(app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    main(reload=True)
