

from typing import Any, Dict, TypedDict
import json
from shared.extraction_llm import extract_leave_request_llm
from shared.intent_llm import classify_intent_llm
from shared.email_outbox import EmailOutbox
from agent_app.mcpClient import get_mcp_tool_by_name
from shared.friendly_message_llm import friendly_message_lln
from shared.friendly_message_llm_success import friendly_message_lln_success


# -----------------------------
# LangGraph State
# -----------------------------
class AgentState(TypedDict, total=False):
    email_from: str
    email_body: str
    intent: str                 # "balance" | "create_loa" | "unknown"
    missing: list[str]          # missing fields like ["start_date","end_date"]
    last_answer: str            # what we told user last
    req: Any  # LeaveRequest (pydantic)
    validation: Dict[str, Any]
    balance: Dict[str, Any]
    transaction_id: str
    status: str
    ok: bool
    message: str

def normalize_tool_output(raw: Any) -> Dict[str, Any]:
    """
    Normalize MCP tool output to a dict.

    Handles:
    - dict already (normal)
    - list[dict]
    - langchain-style content blocks: {"type":"text","text":"{...json...}"}
    - wrappers: {"content":[{...}]}
    """
    if raw is None:
        return {}
    if isinstance(raw, list):
        if not raw:
            return {}
        return normalize_tool_output(raw[0])

    if isinstance(raw, dict) and "content" in raw and isinstance(raw["content"], list) and raw["content"]:
        return normalize_tool_output(raw["content"][0])

    if isinstance(raw, dict) and raw.get("type") == "text" and isinstance(raw.get("text"), str):
        text = raw["text"].strip()
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
            return {"value": obj}
        except json.JSONDecodeError:
            return {"text": text}
    if isinstance(raw, dict):
        for key in ("result", "data", "output"):
            if key in raw:
                return normalize_tool_output(raw[key])
        return raw

    return {"value": raw}



# -----------------------------
# Graph Nodes
# -----------------------------
async def node_extract(state: AgentState) -> AgentState:
    """
    LLM extraction node.
    Your extraction_llm.py should force ISO dates (YYYY-MM-DD).
    """
    req = await extract_leave_request_llm(
        email_from=state["email_from"],
        email_body=state["email_body"],
    )
    return {"req": req}


async def node_validate(state: AgentState) -> AgentState:
    tool_by_name = await get_mcp_tool_by_name()

    req = state.get("req")  # may be missing for balance intent
    employee_email = (
        str(req.employee_email) if req and getattr(req, "employee_email", None)
        else str(state.get("email_from"))
    )

    raw = await tool_by_name["validate_employee"].ainvoke(
        {"employee_email": employee_email}
    )
    validation = normalize_tool_output(raw)

    print("[graph] validate_employee raw:", type(raw), raw)
    print("[graph] validate_employee normalized:", validation)

    return {"validation": validation}



async def node_balance(state: AgentState) -> AgentState:
    tool_by_name = await get_mcp_tool_by_name()

    req = state.get("req")  # may be missing for balance intent
    employee_email = (
        str(req.employee_email) if req and getattr(req, "employee_email", None)
        else str(state.get("email_from"))
    )

    raw = await tool_by_name["get_leave_balance"].ainvoke(
        {"employee_email": employee_email}
    )
    balance = normalize_tool_output(raw)

    print("[graph] get_leave_balance raw:", type(raw), raw)
    print("[graph] get_leave_balance normalized:", balance)

    return {"balance": balance}




async def node_create_loa(state: AgentState) -> AgentState:
    req = state.get("req")
    validation = state.get("validate_employee") or {}
    balance = state.get("get_leave_balance") or {}
    if not req:
        return {"ok": False, "message": "Missing leave details. Please provide start and end date."}

    tool_by_name = await get_mcp_tool_by_name()
    if not validation.get("ok_to_create_loa", False):
        email = validation.get("employee_email") or state.get("employee_email")
        if validation.get("currently_on_leave"):
            msg = (
                f"{email} appears to be currently on leave, so I can’t create a new LOA request yet. "
                f"Please check existing leave dates in Workday or provide updated dates."
            )
        elif not validation.get("active"):
            msg = f"{email} is not an active employee, so I can’t create an LOA request."
        else:
            msg = f"{email} is not eligible to create LOA right now."

        return {
            "final_message": msg,
            "loa_created": False,
        }

    raw = await tool_by_name["create_loa"].ainvoke(
        {
            "employee_email": str(req.employee_email),
            "start_date": req.start_date.isoformat(),
            "end_date": req.end_date.isoformat(),
            "employee_name": req.employee_name,
            "reason": req.reason,
        }
    )
    data = normalize_tool_output(raw)
    return {"transaction_id": data["transaction_id"], "status": data["status"]}



async def node_email_success(state: AgentState) -> AgentState:
    req = state["req"]
    balance = state.get("balance", {})
    validation = state.get("validation", {})    
    outbox = EmailOutbox()


    employee_name = getattr(req, "employee_name", "") if req else ""
    start_date = getattr(req, "start_date", None) if req else None
    end_date = getattr(req, "end_date", None) if req else None
    reason = getattr(req, "reason", None) if req else None

    employee_email = (
        str(req.employee_email) if req and getattr(req, "employee_email", None)
        else str(state.get("email_from", ""))
    )

    prompt_vars = {
        "employee_email": employee_email,
        "employee_name": employee_name or "there",
        "start_date": str(start_date) if start_date else "N/A",
        "end_date": str(end_date) if end_date else "N/A",
        "reason": reason or "N/A",
        "active": validation.get("active"),
        "currently_on_leave": validation.get("currently_on_leave"),
        "balance_days": balance.get("balance_days", "N/A"),
    }

    # ✅ LLM creates a user-friendly message
    # llm_msg = await llm.ainvoke(FAILURE_PROMPT.format_messages(**prompt_vars))
    # friendly_text = llm_msg.content.strip()

    friendly_text=await friendly_message_lln_success(prompt_vars)

    
    outbox.send(
        to=employee_email,
        subject="Leave of Absence Created (In Review)",
        body=f"Hi {employee_name or ''},\n\n{friendly_text}\n\nThanks,\nHR Leave Assistant",
    )

    # ✅ Return the real message to UI
    return {"ok": True, "message": friendly_text, "email_sent": True}




# async def node_email_failure(state: AgentState) -> AgentState:
#     req = state.get("req")
#     validation = state.get("validation", {})
#     outbox = EmailOutbox()

#     employee_email = (
#         str(req.employee_email) if req and getattr(req, "employee_email", None)
#         else str(state.get("email_from", ""))
#     )

#     # If intent is unknown, just respond in chat (don’t send email)
#     if state.get("intent") == "unknown":
#         return {
#             "ok": False,
#             "message": "I can help with leave balance or creating a leave request. Try: 'what is my leave balance?' or 'create leave 2026-03-01 to 2026-03-03'."
#         }

#     # If we *are* failing create_loa validation, then send email
#     outbox.send(
#         to=employee_email,
#         subject="Leave of Absence Request - Action Needed",
#         body=(
#             f"Hi {getattr(req, 'employee_name', '') if req else ''},\n\n"
#             f"We could not create your LOA.\n"
#             f"Active: {validation.get('active')}, "
#             f"On leave: {validation.get('currently_on_leave')}\n\n"
#             f"Please contact HR.\n"
#         ),
#     )

#     return {"ok": False, "message": "Validation failed; email sent to employee."}

async def node_email_failure(state: AgentState) -> AgentState:
    req = state.get("req")
    validation = state.get("validation", {})          # or validate_employee
    balance = state.get("get_leave_balance", {})      # if you have it
    outbox = EmailOutbox()

    employee_email = (
        str(req.employee_email) if req and getattr(req, "employee_email", None)
        else str(state.get("email_from", ""))
    )

    # If intent is unknown -> chat message only
    if state.get("intent") == "unknown":
        msg = (
            "I can help with leave balance or creating a leave request.\n\n"
            "Try:\n"
            "- “what is my leave balance?”\n"
            "- “leave from 2026-03-01 to 2026-03-03”"
        )
        return {"ok": False, "message": msg}

    # Build inputs for LLM
    employee_name = getattr(req, "employee_name", "") if req else ""
    start_date = getattr(req, "start_date", None) if req else None
    end_date = getattr(req, "end_date", None) if req else None
    reason = getattr(req, "reason", None) if req else None

    prompt_vars = {
        "employee_email": employee_email,
        "employee_name": employee_name or "there",
        "start_date": str(start_date) if start_date else "N/A",
        "end_date": str(end_date) if end_date else "N/A",
        "reason": reason or "N/A",
        "active": validation.get("active"),
        "currently_on_leave": validation.get("currently_on_leave"),
        "balance_days": balance.get("balance_days", "N/A"),
    }

    # ✅ LLM creates a user-friendly message
    # llm_msg = await llm.ainvoke(FAILURE_PROMPT.format_messages(**prompt_vars))
    # friendly_text = llm_msg.content.strip()

    friendly_text=await friendly_message_lln(prompt_vars)

    # Send email with same friendly text
    outbox.send(
        to=employee_email,
        subject="Leave of Absence Request - Action Needed",
        body=f"Hi {employee_name or ''},\n\n{friendly_text}\n\nThanks,\nHR Leave Assistant",
    )

    # ✅ Return the real message to UI
    return {"ok": False, "message": friendly_text, "email_sent": True}




async def node_route_intent(state: AgentState) -> AgentState:
    print("TEST#######",state)
    text = state.get("email_body", "")
    email_from = state.get("email_from", "")
    out = await classify_intent_llm(email_from=email_from, text=text)
    # Optional debug
    print("[intent-llm]", out.intent, out.confidence, out.reason)
    return {"intent": out.intent}




def route_after_validate(state: AgentState) -> str:
    validation = state.get("validation", {})
    return "balance" if validation.get("ok_to_create_loa") else "email_failure"


def route_after_intent(state: AgentState) -> str:
    intent = state.get("intent", "unknown")
    if intent == "balance":
        return "validate"
    if intent == "create_loa":
        return "extract"
    return "email_failure"   # or a new "ask_clarify" node


async def node_reply_balance(state: AgentState) -> AgentState:
    bal = state.get("balance", {})
    days = bal.get("balance_days")
    msg = f"Your current leave balance is {days} day(s)." if days is not None else "I couldn’t fetch your balance."
    return {"ok": True, "message": msg}


def route_after_balance(s: dict) -> str:
    if s.get("intent") == "balance":
        return "reply_balance"

    ve = s.get("validate_employee") or {}
    if ve.get("ok_to_create_loa") is True:
        return "create_loa"

    return "email_failure"




def route_after_create_loa(s: dict) -> str:
    return "email_success" if s.get("loa_created") is True else "email_failure"
