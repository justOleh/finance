"""
backend.main
------------
FastAPI application entry-point for the My Finance backend API.

This module wires together the database, routers, and middleware and is the
file passed to ``uvicorn`` at startup.

On startup (lifespan):
- Creates the ``data/receipts/`` directory if it does not exist.
- Runs ``Base.metadata.create_all`` to create any missing database tables.

CORS
~~~~
All origins are allowed during development.  Restrict ``allow_origins`` to
your frontend domain before deploying to a public server.

Routers
~~~~~~~
- ``/expenses`` — CRUD for expense records (``routers.expenses``)
- ``/receipts`` — Receipt image upload and parsing (``routers.receipts``)

API docs (when running)
~~~~~~~~~~~~~~~~~~~~~~~
- Swagger UI : http://localhost:8000/docs
- ReDoc      : http://localhost:8000/redoc
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from routers.expenses import router as expenses_router
from routers.receipts import router as receipts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create required directories and database tables on startup."""
    Path("./data/receipts").mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="My Finance API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(expenses_router)
app.include_router(receipts_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
