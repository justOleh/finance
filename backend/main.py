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
