from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.session import ensure_table
from app.api.v1.expenses import router as expenses_router
from app.api.v1.receipts import router as receipts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path("./data/receipts").mkdir(parents=True, exist_ok=True)
    if settings.dynamodb_endpoint_url:  # DynamoDB Local: no Terraform to create the table
        ensure_table()
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
