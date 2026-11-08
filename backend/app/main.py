from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.expenses import router as expenses_router
from app.api.v1.receipts import router as receipts_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path("./data/receipts").mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="My Finance API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Empty CORS_ORIGINS (local docker-compose, same-origin via nginx) => no cross-origin access.
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(expenses_router)
app.include_router(receipts_router)


@app.get("/")
def root():
    return {
        "service": "my-finance-backend",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}
