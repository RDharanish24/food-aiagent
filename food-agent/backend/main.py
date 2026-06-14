import asyncio
import sys

# ✅ MUST be first
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.database import connect_to_mongo, close_mongo_connection
from api.chat import router as chat_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(title="Swiggy AI Agent Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api/chat", tags=["chat"])

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Swiggy AI Backend (Python)"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)