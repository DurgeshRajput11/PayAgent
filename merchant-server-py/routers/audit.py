"""
routers/audit.py — mirrors internal/handlers/audit.go
GET  /audit/{session_id}  → GetBySession
POST /api/v1/audit         → WriteAudit
GET  /sessions             → ListSessions
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from models import AuditLog
from services.audit import AuditService

router = APIRouter(tags=["audit"])


class WriteAuditRequest(BaseModel):
    session_id: str
    event_type: str
    actor:      str
    reasoning:  str = ""
    outcome:    str = ""


@router.get("/api/v1/audit/{session_id}")
async def get_by_session(session_id: str, request: Request):
    audit_svc: AuditService = request.app.state.audit_svc
    logs = await audit_svc.get_by_session(session_id)
    return {"logs": [l.model_dump(mode="json") for l in logs], "total": len(logs)}


@router.post("/api/v1/audit")
async def write_audit(body: WriteAuditRequest, request: Request):
    audit_svc: AuditService = request.app.state.audit_svc
    await audit_svc.write(AuditLog(
        session_id=body.session_id,
        event_type=body.event_type,
        actor=body.actor,
        reasoning=body.reasoning,
        outcome=body.outcome,
    ))
    return {"status": "ok"}


@router.get("/sessions")
async def list_sessions(request: Request):
    audit_svc: AuditService = request.app.state.audit_svc
    sessions = await audit_svc.list_sessions()
    return {"sessions": sessions}