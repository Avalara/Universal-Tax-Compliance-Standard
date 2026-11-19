"""HTTP process for the mock tax server."""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from bindings.ucp.router import create_router
from examples.ucp.determine import MockDeterminer


def create_app(determiner: MockDeterminer | None = None) -> FastAPI:
    app = FastAPI(
        title="UTCS UCP tax example",
        description="Mock determination provider behind the dev.ucp.shopping.tax binding.",
        version="0.1.0",
    )
    app.state.determiner = determiner or MockDeterminer()
    app.include_router(create_router(app.state.determiner))

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def main() -> None:
    host = os.environ.get("UTCS_REST_HOST", "127.0.0.1")
    port = int(os.environ.get("UTCS_REST_PORT", "8080"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
