import hmac
import uuid
from contextlib import asynccontextmanager
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage
import os
import json
from datetime import datetime
import time
import redis as redis_lib
from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.checkpoint.memory import MemorySaver

from agent.workflow import create_workflow
from agent.state import AgentState

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis_lib.from_url(REDIS_URL)

# AGENT_SERVICE_API_KEY secures every route below. Previously this FastAPI
# service had no authentication at all: /agent/run, /agent/{id}/message,
# /agent/{id}/state and — most importantly — /agent/{id}/resume (the
# endpoint that approves spending real money) were reachable by anyone who
# could route to this service, with nothing to check.
AGENT_SERVICE_API_KEY = os.getenv("AGENT_SERVICE_API_KEY", "dev-agent-key")


async def verify_internal_key(x_internal_key: str = Header(default="")):
    if not hmac.compare_digest(x_internal_key, AGENT_SERVICE_API_KEY):
        raise HTTPException(status_code=401, detail="UNAUTHORIZED")


router = APIRouter(dependencies=[Depends(verify_internal_key)])
build_graph = create_workflow()

graph = None

@asynccontextmanager
async def lifespan(app):
    global graph
    try:
        async with AsyncRedisSaver.from_conn_string(REDIS_URL) as checkpointer:
            await checkpointer.asetup()
            graph = build_graph(checkpointer)
            yield
    except Exception as e:
        print(f"Redis checkpointer failed ({e}), falling back to MemorySaver")
        graph = build_graph(MemorySaver())
        yield


def is_user_facing_ai_message(msg) -> bool:
    """Return True only for plain assistant replies, never tool calls/results."""
    if getattr(msg, "type", None) != "ai":
        return False
    if getattr(msg, "tool_calls", None):
        return False
    content = getattr(msg, "content", None)
    return isinstance(content, str) and bool(content.strip())


def format_chat_messages(messages: list) -> list[str]:
    """Keep internal tool payloads out of the chat API response."""
    return [msg.content for msg in messages if is_user_facing_ai_message(msg)]


def publish_events(session_id: str, messages: list):
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                event = {
                    "session_id": session_id,
                    "event_type": f"TOOL_CALL_{tc['name'].upper()}",
                    "actor": "agent",
                    "reasoning": f"Called {tc['name']} with {json.dumps(tc['args'])}",
                    "outcome": "invoked",
                    "created_at": datetime.utcnow().isoformat(),
                }
                redis_client.publish(f"audit:{session_id}", json.dumps(event))
    
    last_msg = messages[-1] if messages else None
    if is_user_facing_ai_message(last_msg):
        event = {
            "session_id": session_id,
            "event_type": "AGENT_RESPONSE",
            "actor": "agent",
            "reasoning": last_msg.content,
            "outcome": "completed",
            "created_at": datetime.utcnow().isoformat(),
        }
        redis_client.publish(f"audit:{session_id}", json.dumps(event))


class RunRequest(BaseModel):
    goal: str
    budget: int = 5000
    session_id: str | None = None


class ResumeRequest(BaseModel):
    decision: str


@router.post("/agent/run")
async def run_agent(req: RunRequest):
    session_id = req.session_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": session_id}}

    event = {
        "session_id": session_id,
        "event_type": "USER_GOAL",
        "actor": "user",
        "reasoning": req.goal,
        "outcome": "started",
        "created_at": datetime.utcnow().isoformat(),
    }
    redis_client.publish(f"audit:{session_id}", json.dumps(event))

    initial_state: AgentState = {
        "session_id": session_id,
        "goal": req.goal,
        "budget": req.budget,
        "messages": [HumanMessage(content=f"Shopping goal: {req.goal}. My budget is ₹{req.budget}. My session ID is {session_id}.")],
        "cart": {},
        "wishlist": [],
        "pending_action": None,
        "decision": None,
        "completed": False,
        "guardrail": None,
    }

    # Execute the LangGraph state machine. If an interrupt occurs (e.g., human-in-the-loop approval),
    # the graph will pause and return the current state, awaiting a `/resume` call.
    result = await graph.ainvoke(initial_state, config=config)

    state_snapshot = await graph.aget_state(config)
    is_interrupted = bool(state_snapshot.tasks)

    messages = result.get("messages", [])
    publish_events(session_id, messages)
    
    if is_interrupted:
        event = {
            "session_id": session_id,
            "event_type": "APPROVAL_REQUIRED",
            "actor": "system",
            "reasoning": "Agent paused for human approval to create order.",
            "outcome": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        redis_client.publish(f"audit:{session_id}", json.dumps(event))

    # Aggregate token usage across all LLM messages in the current run for observability
    total_input_tokens = 0
    total_output_tokens = 0
    for msg in result.get("messages", []):
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)

    return {
        "session_id": session_id,
        "budget": req.budget,
        "status": "awaiting_approval" if is_interrupted else "completed",
        "messages": format_chat_messages(result.get("messages", [])),
        "token_usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "estimated_cost_usd": round((total_input_tokens * 0.0000005 + total_output_tokens * 0.000001), 6),
        }
    }


@router.post("/agent/{session_id}/resume")
async def resume_agent(session_id: str, req: ResumeRequest):
    config = {"configurable": {"thread_id": session_id}}

    state_snapshot = await graph.aget_state(config)
    if not state_snapshot.tasks:
        raise HTTPException(status_code=404, detail="No interrupted agent found for this session")

    # Update the state with the human decision
    await graph.aupdate_state(config, {"decision": req.decision})
    
    # Resume the graph from the paused node
    result = await graph.ainvoke(None, config=config)

    messages = result.get("messages", [])
    publish_events(session_id, messages)

    total_input_tokens = 0
    total_output_tokens = 0
    for msg in result.get("messages", []):
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)

    return {
        "session_id": session_id,
        "status": "completed",
        "decision": req.decision,
        "messages": format_chat_messages(result.get("messages", [])),
        "token_usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "estimated_cost_usd": round((total_input_tokens * 0.0000005 + total_output_tokens * 0.000001), 6),
        }
    }


class MessageRequest(BaseModel):
    message: str

@router.post("/agent/{session_id}/message")
async def send_message(session_id: str, req: MessageRequest):
    config = {"configurable": {"thread_id": session_id}}
    
    state_snapshot = await graph.aget_state(config)
    if not state_snapshot:
        raise HTTPException(status_code=404, detail="Session not found")
        
    try:
        started = time.perf_counter()
        print(f"[LATENCY] message workflow started: session={session_id}")

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=req.message)]},
            config=config,
        )

        elapsed = time.perf_counter() - started
        print(
            f"[LATENCY] graph.ainvoke completed in {elapsed:.2f}s "
            f"for session={session_id}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")
    
    new_snapshot = await graph.aget_state(config)
    is_interrupted = bool(new_snapshot.tasks)

    messages = result.get("messages", [])
    publish_events(session_id, messages)
    
    total_input_tokens = 0
    total_output_tokens = 0
    for msg in result.get("messages", []):
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)

    return {
        "session_id": session_id,
        "status": "awaiting_approval" if is_interrupted else "completed",
        "messages": format_chat_messages(result.get("messages", [])),
        "token_usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "estimated_cost_usd": round((total_input_tokens * 0.0000005 + total_output_tokens * 0.000001), 6),
        }
    }

@router.get("/agent/{session_id}/state")
async def get_state(session_id: str):
    config = {"configurable": {"thread_id": session_id}}
    state_snapshot = await graph.aget_state(config)
    if not state_snapshot:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages_formatted = []
    total_input_tokens = 0
    total_output_tokens = 0

    for msg in state_snapshot.values.get("messages", []):
        if msg.type == "human":
            content = msg.content
            if content.startswith("Shopping goal: "):
                messages_formatted.append(f"USER: {content.split('. My session ID')[0].replace('Shopping goal: ', '')}")
            else:
                messages_formatted.append(f"USER: {content}")
        elif is_user_facing_ai_message(msg):
            messages_formatted.append(msg.content)
            
        usage = getattr(msg, "usage_metadata", None)
        if usage:
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)

    return {
        "session_id": session_id,
        "goal": state_snapshot.values.get("goal", ""),
        "status": "awaiting_approval" if bool(state_snapshot.tasks) else "completed",
        "messages": messages_formatted,
        "token_usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "estimated_cost_usd": round((total_input_tokens * 0.0000005 + total_output_tokens * 0.000001), 6),
        }
    }
