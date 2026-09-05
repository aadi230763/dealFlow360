import json

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.core.events import subscribe
from app.core.security import decode_token

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/stream")
async def stream(request: Request, token: str = Query(...)):
    try:
        decode_token(token, audience="internal")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    async def gen():
        async for event in subscribe():
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
