import asyncio
import os
import logging
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-10s  %(message)s",
    datefmt="%H:%M:%S",
)
# Quieten noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from routes.dashboard import router as dashboard_router
from routes.chat import router as chat_router
from agent import prewarm_docs_cache, refresh_docs_cache

app = FastAPI(title="Qualys CS Intelligence", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(prewarm_docs_cache())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(chat_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/docs/refresh")
async def refresh_docs(background_tasks: BackgroundTasks):
    """Trigger a background refresh of the docs cache."""
    background_tasks.add_task(refresh_docs_cache)
    return {"message": "Docs cache refresh started"}
