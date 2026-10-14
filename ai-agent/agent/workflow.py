import os
import json
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt

from agent.state import AgentState
from agent.tools import TOOLS

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

SYSTEM_PROMPT = """You are PayAgent, a smart and conversational AI shopping assistant for a large multi-category e-commerce store.

Your catalog has 140+ real products across 15 categories:
- **smartphones** — Redmi, Realme, Samsung, OnePlus, iPhone, Poco, Moto, Vivo, Oppo, iQOO
- **laptops** — Dell, HP, Lenovo, Asus, MacBook, Acer, MSI
- **electronics** — earbuds, headphones, speakers, TVs, projectors, cameras, printers, routers, smart bulbs
- **gaming** — PS5 controller, Xbox controller, gaming mice, keyboards, headsets, gaming chairs, Nintendo Switch
- **shoes** — running, casual, formal, sneakers, slippers, sports — Nike, Adidas, Puma, Bata, Woodland, Crocs, Hoka, Converse
- **clothing** — jeans, kurta, t-shirts, jackets, hoodies, formals, ethnic, sportswear, sherwani
- **bags** — backpacks, trolleys, sling bags, messenger bags, wallets, gym bags
- **watches** — smartwatches, analog, G-Shock, Apple Watch, Titan, Casio, Fossil
- **sports** — dumbbells, yoga mats, protein supplements, cricket bat, badminton, resistance bands
- **beauty** — face wash, sunscreen, shampoo, moisturizer, trimmer, hair dryer, face pack, hair color
- **home-kitchen** — air fryer, mixer grinder, OTG oven, water purifier, kettle, cookware, vacuum, refrigerator, washing machine
- **books** — tech, self-help, fiction, finance, business, history, programming
- **toys** — LEGO, UNO, board games, RC car
- **stationery** — pens, pencils, notebooks, calculators
- **home-decor** — photo frames, smart bulbs, wall hanging, shelf units

## Core Rules
1. ALWAYS use `catalog_search` before suggesting or adding any product. Never invent products.
2. Be conversational. Ask clarifying questions if the user's intent is vague.
3. Use the exact product IDs returned by search when calling other tools.
4. Keep responses concise, friendly, and formatted clearly (use bullet points or tables for comparisons).

## What You Can Do — Scenario Guide

### Search & Browse
- "Show me running shoes" → `catalog_search(query="running shoes")`
- "What bags do you have under ₹1200?" → `catalog_search(category="bags", max_price_inr=1200)`
- "Show me all electronics" → `catalog_search(category="electronics")`
- "Find me something under ₹500" → `catalog_search(max_price_inr=500)`

### Compare Products
- "Compare the two bags" / "Which is better, X or Y?" → Use `catalog_compare([id1, id2])` and present a clear side-by-side table showing: name, price, stock, description, and tags.
- Always end a comparison with a recommendation and ask if the user wants to add one.

### Product Details
- "Tell me more about the Nike shoes" / "What are the specs of X?" → `catalog_get_product(product_id)`
- Surface: full description, price, stock availability, category, tags.

### Cart Management
- "Add the cheaper one" → `cart_add(session_id, product_id, quantity=1, reasoning="...")`
- "Add 2 of those" → `cart_add(session_id, product_id, quantity=2, reasoning="...")`
- "Add 1 more" / "Increase quantity" → `cart_add` with the DIFFERENCE in quantity
- "Remove the bag" / "I don't want X anymore" → `cart_remove(session_id, product_id)`
- "Clear my cart" / "Start over" → `cart_clear(session_id)`
- "What's in my cart?" / "Show my cart" → `cart_get(session_id)` then format clearly

### Wishlist (Save for Later)
- "Save this for later" / "Add to wishlist" → Acknowledge and remember the product name in your response. Tell the user it's saved in their wishlist for this session.
- "What's in my wishlist?" → List the items the user has mentioned saving.

### Stock Checks
- "Is this in stock?" / "How many left?" → `catalog_get_product(product_id)` and report the `stock` field.
- If stock is 0 or low (< 3), proactively warn the user.

### Checkout & Payment
- ONLY call `razorpay_create_order` when the user says "buy", "checkout", "pay", "place order", or equivalent.
- Before creating the order, always call `cart_get` to confirm the total amount in paise.
- You MUST stop and wait for human approval after calling `razorpay_create_order`. Do not proceed until approved.

### Handling Issues
- "I changed my mind" → Offer to remove specific items or clear the whole cart.
- Product not found → Tell the user clearly and offer alternatives in the same category.
- Out of stock → Apologize and suggest similar in-stock alternatives using `catalog_search`.
- Order over ₹{BUDGET} → The guardrail will block it automatically. Explain this to the user.

## Response Formatting
- Use ₹ for prices (not INR)
- Use markdown tables for comparisons
- Always confirm actions: "Added X (₹Y) to your cart."
"""


def create_workflow():
    llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
    llm_with_tools = llm.bind_tools(TOOLS)

    from tenacity import retry, wait_exponential, stop_after_attempt

    # Exponential backoff prevents fatal application crashes when hitting LLM API rate limits.
    @retry(wait=wait_exponential(multiplier=1, min=2, max=15), stop=stop_after_attempt(5))
    def invoke_llm_with_retry(messages):
        return llm_with_tools.invoke(messages)

    from langchain_core.runnables import RunnableConfig
    from agent.tools import cart_get
    
    def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        budget = state.get("budget", 5000)
        system_prompt = SYSTEM_PROMPT.replace("{BUDGET}", str(budget))
        
        session_id = config.get("configurable", {}).get("thread_id")
        if session_id:
            try:
                # Dynamically injecting live cart state from Redis on every turn
                # guarantees the LLM never hallucinates out-of-band UI quantity changes.
                cart_data = cart_get.invoke({"session_id": session_id})
                if isinstance(cart_data, dict) and "error" not in cart_data:
                    cart_summary = json.dumps(cart_data, indent=2)
                    system_prompt += f"\n\n--- CURRENT CART STATE ---\n{cart_summary}\n--------------------------\n"
            except Exception as e:
                print(f"Failed to fetch cart state: {e}")

        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        response = invoke_llm_with_retry(messages)
        return {"messages": [response]}

    def human_approval_node(state: AgentState) -> dict:
        # The graph pauses BEFORE this node due to interrupt_before=["human_approval"].
        # When /resume is called, it passes {"decision": "approved"} as state update.
        # So we just pass the decision forward.
        print(f"DEBUG human_approval_node executing. Decision in state: {state.get('decision')}")
        return {"decision": state.get("decision")}

    import httpx
    from langchain_core.messages import AIMessage
    
    MERCHANT_BASE_URL = os.getenv("MERCHANT_BASE_URL", "http://localhost:8080")
    MERCHANT_API_KEY = os.getenv("MERCHANT_API_KEY", "internal-agent-api-key-change-in-prod")
    HEADERS = {"X-API-Key": MERCHANT_API_KEY, "Content-Type": "application/json"}

    from langchain_core.runnables import RunnableConfig
    def guardrail_node(state: AgentState, config: RunnableConfig) -> dict:
        """Check the cart total and reject if it exceeds the spending limit."""
        messages = state["messages"]
        last = messages[-1] if messages else None
        
        budget = state.get("budget", 5000)
        
        if last and hasattr(last, "tool_calls"):
            for tc in last.tool_calls:
                if tc["name"] == "razorpay_create_order":
                    amount_paise = tc["args"].get("amount_paise", 0)
                    amount_inr = amount_paise / 100
                    if amount_inr > budget:
                        rejection = AIMessage(content=f"GUARDRAIL: Order of ₹{amount_inr:.2f} exceeds the spending limit of ₹{budget:.2f}. Order automatically rejected for safety.")

                        # NOTE: this previously referenced an undefined
                        # MAX_ORDER_INR name, which raised a NameError that
                        # the surrounding try/except silently swallowed — so
                        # the one audit event you'd most want (a guardrail
                        # actually firing) was never written. Fixed to use
                        # the actual per-request `budget`.
                        try:
                            session_id = config.get("configurable", {}).get("thread_id")
                            if session_id:
                                httpx.post(f"{MERCHANT_BASE_URL}/api/v1/audit", json={
                                    "session_id": session_id,
                                    "event_type": "GUARDRAIL_TRIGGERED",
                                    "actor": "system",
                                    "reasoning": f"Order of ₹{amount_inr:.2f} exceeds limit of ₹{budget:.2f}",
                                    "outcome": "blocked"
                                }, headers=HEADERS, timeout=5)
                        except Exception as e:
                            print(f"Failed to post guardrail audit event: {e}")
                            
                        return {"messages": [rejection], "completed": True, "guardrail": "blocked"}
        
        return {"guardrail": "passed"}

    def should_interrupt(state: AgentState) -> str:
        messages = state["messages"]
        last = messages[-1] if messages else None
        if not last or not hasattr(last, "tool_calls"):
            return "end"

        tool_names = [tc["name"] for tc in last.tool_calls]

        if "razorpay_create_order" in tool_names:
            return "approval"

        if last.tool_calls:
            return "tools"

        return "end"
        
    def check_guardrail_result(state: AgentState) -> str:
        if state.get("guardrail") == "blocked":
            return "blocked"
        return "passed"

    def after_approval(state: AgentState) -> str:
        print(f"DEBUG after_approval executing. Decision in state: {state.get('decision')}")
        if state.get("decision") == "approved":
            return "tools"
        return "rejected"

    def rejected_node(state: AgentState, config: RunnableConfig) -> dict:
        # Previously a "rejected" decision just routed straight to END with
        # no message and no audit trail — the user got silence, and the
        # audit log had no record the order was ever declined.
        message = AIMessage(content="Order cancelled — you rejected the payment approval. Let me know if you'd like to change anything in your cart.")

        try:
            session_id = config.get("configurable", {}).get("thread_id")
            if session_id:
                httpx.post(f"{MERCHANT_BASE_URL}/api/v1/audit", json={
                    "session_id": session_id,
                    "event_type": "ORDER_REJECTED",
                    "actor": "user",
                    "reasoning": "User declined the payment approval request",
                    "outcome": "rejected",
                }, headers=HEADERS, timeout=5)
        except Exception as e:
            print(f"Failed to post rejection audit event: {e}")

        return {"messages": [message], "completed": True}


    def build_graph(checkpointer):
        builder = StateGraph(AgentState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", ToolNode(TOOLS))
        builder.add_node("guardrail", guardrail_node)
        builder.add_node("human_approval", human_approval_node)
        builder.add_node("rejected_node", rejected_node)
        

        builder.set_entry_point("agent")
        builder.add_conditional_edges("agent", should_interrupt, {
            "tools": "tools",
            "approval": "guardrail",
            "end": END,
        })
        builder.add_edge("tools", "agent")
        builder.add_conditional_edges("guardrail", check_guardrail_result, {
            "blocked": END,
            "passed": "human_approval",
        })
        builder.add_conditional_edges("human_approval", after_approval, {
            "tools": "tools",
            "rejected": "rejected_node",
        })
        return builder.compile(checkpointer=checkpointer, interrupt_before=["human_approval"])

    return build_graph