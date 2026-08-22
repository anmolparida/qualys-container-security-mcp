from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agent import run_agent

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    history: list = []


@router.post("/")
async def chat(req: ChatRequest):
    async def generate():
        try:
            async for chunk in run_agent(req.message, req.history):
                yield chunk
        except Exception as e:
            yield f"\n__ERROR__:{str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")
