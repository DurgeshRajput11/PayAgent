from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    session_id: str
    goal: str
    budget: int
    messages: Annotated[list, add_messages]
    cart: dict
    wishlist: list
    pending_action: dict | None
    decision: str | None
    completed: bool
    guardrail: str | None