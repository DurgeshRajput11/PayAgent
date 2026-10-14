"""
routers/resume.py — mirrors internal/handlers/resume.go

POST /agent/{session_id}/resume

Forwards the approval/rejection decision to the Python ai-agent service.
Uses httpx (async) instead of Go's http.DefaultClient.
"""
import json
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

log    = logging.getLogger(__name__)
router = APIRouter(tags=["resume"])


class ResumeRequest(BaseModel):
    decision: str

    @field_validator("decision")
    @classmethod
    def must_be_valid(cls, v: str) -> str:
        if v not in ("approved", "rejected"):
            raise ValueError("decision must be 'approved' or 'rejected'")
        return v


@router.post("/agent/{session_id}/resume")
async def resume(session_id: str, body: ResumeRequest, request: Request):
    from config import cfg

    agent_url = cfg.agent_service_url
    agent_key = cfg.agent_service_key

    payload = json.dumps({"decision": body.decision})

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{agent_url}/agent/{session_id}/resume",
                content=payload,
                headers={
                    "Content-Type":   "application/json",
                    "X-Internal-Key": agent_key,
                },
            )
    except httpx.RequestError as exc:
        log.error("Resume: failed to reach agent service: %s", exc)
        raise HTTPException(status_code=502, detail={"error": "AGENT_RESUME_FAILED"})

    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail={"error": "AGENT_RESUME_FAILED"})

    return {"status": "resumed", "session_id": session_id, "decision": body.decision}