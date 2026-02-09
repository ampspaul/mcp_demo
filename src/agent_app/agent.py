# src/agent_app/agent.py
import asyncio
from typing import Any, Dict, TypedDict
import json
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_mcp_adapters.client import MultiServerMCPClient

from shared.settings import settings
from shared.extraction_llm import extract_leave_request_llm
from shared.workday_client import WorkdayClient
from shared.email_outbox import EmailOutbox
from agent_app.mcpClient import get_mcp_tool_by_name

load_dotenv() 


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

    # If list, normalize first element
    if isinstance(raw, list):
        if not raw:
            return {}
        return normalize_tool_output(raw[0])

    # If dict wrapper with "content"
    if isinstance(raw, dict) and "content" in raw and isinstance(raw["content"], list) and raw["content"]:
        return normalize_tool_output(raw["content"][0])

    # If it's a text-block dict
    if isinstance(raw, dict) and raw.get("type") == "text" and isinstance(raw.get("text"), str):
        text = raw["text"].strip()
        # Try parse JSON
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return obj
            return {"value": obj}
        except json.JSONDecodeError:
            # Not JSON, return as-is
            return {"text": text}

    # If plain dict, but nested wrappers like result/data/output
    if isinstance(raw, dict):
        for key in ("result", "data", "output"):
            if key in raw:
                return normalize_tool_output(raw[key])
        return raw

    # Fallback
    return {"value": raw}




# -----------------------------
# LangGraph State
# -----------------------------
class AgentState(TypedDict, total=False):
    # input
    email_from: str
    email_body: str

    # extracted
    req: Any  # LeaveRequest (pydantic)

    # tools
    validation: Dict[str, Any]
    balance: Dict[str, Any]

    # workday
    transaction_id: str
    status: str

    # output
    ok: bool
    message: str


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
    req = state["req"]
    tool_by_name = await get_mcp_tool_by_name()  # ✅ FIX: not from state

    raw = await tool_by_name["validate_employee"].ainvoke(
        {"employee_email": str(req.employee_email)}
    )
    validation = normalize_tool_output(raw)

    print("[graph] validate_employee raw:", type(raw), raw)
    print("[graph] validate_employee normalized:", validation)

    return {"validation": validation}


async def node_balance(state: AgentState) -> AgentState:
    req = state["req"]
    tool_by_name = await get_mcp_tool_by_name()

    raw = await tool_by_name["get_leave_balance"].ainvoke(
        {"employee_email": str(req.employee_email)}
    )
    balance = normalize_tool_output(raw)

    print("[graph] get_leave_balance raw:", type(raw), raw)
    print("[graph] get_leave_balance normalized:", balance)

    return {"balance": balance}


# async def node_create_loa(state: AgentState) -> AgentState:
#     req = state["req"]
#     wd = WorkdayClient(settings.workday_api_base_url)
#     resp = await wd.create_loa(req)
#     return {"transaction_id": resp.transaction_id, "status": resp.status}


async def node_create_loa(state: AgentState) -> AgentState:
    req = state["req"]
    tool_by_name = await get_mcp_tool_by_name()

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
    outbox = EmailOutbox()

    outbox.send(
        to=str(req.employee_email),
        subject="Leave of Absence Created (In Review)",
        body=(
            f"Hi {req.employee_name or ''},\n\n"
            f"Your LOA request has been created and is in review.\n\n"
            f"TransactionId: {state.get('transaction_id')}\n"
            f"Status: {state.get('status')}\n"
            f"Requested Dates: {req.start_date} to {req.end_date}\n"
            f"Leave Balance (demo DB): {balance.get('balance_days')} days\n\n"
            f"Thanks,\nHR Automation Bot\n"
        ),
    )
    return {"ok": True, "message": "LOA created and confirmation email sent."}


async def node_email_failure(state: AgentState) -> AgentState:
    req = state["req"]
    validation = state.get("validation", {})
    outbox = EmailOutbox()

    outbox.send(
        to=str(req.employee_email),
        subject="Leave of Absence Request - Action Needed",
        body=(
            f"Hi {req.employee_name or ''},\n\n"
            f"We could not create your LOA.\n"
            f"Active: {validation.get('active')}, "
            f"On leave: {validation.get('currently_on_leave')}\n\n"
            f"Please contact HR.\n"
        ),
    )
    return {"ok": False, "message": "Validation failed; email sent to employee."}


def route_after_validate(state: AgentState) -> str:
    validation = state.get("validation", {})
    print("TEST5555555",validation)
    print("TEST555555--state",state)
    print("TEST555555--balance",validation.get("ok_to_create_loa"))
    return "balance" if validation.get("ok_to_create_loa") else "email_failure"


# -----------------------------
# Build Graph
# -----------------------------
def build_graph():
    g = StateGraph(AgentState)

    g.add_node("extract", node_extract)
    g.add_node("validate", node_validate)
    g.add_node("balance", node_balance)
    g.add_node("create_loa", node_create_loa)
    g.add_node("email_success", node_email_success)
    g.add_node("email_failure", node_email_failure)

    g.set_entry_point("extract")
    g.add_edge("extract", "validate")

    g.add_conditional_edges(
        "validate",
        route_after_validate,
        {"balance": "balance", "email_failure": "email_failure"},
    )

    g.add_edge("balance", "create_loa")
    g.add_edge("create_loa", "email_success")

    g.add_edge("email_success", END)
    g.add_edge("email_failure", END)

    return g.compile()


# -----------------------------
# Main
# -----------------------------
async def main():
    email_from = input("Enter the email from: ").strip()

    # print("Enter the email body (end with an empty line):")
    # lines = []
    # while True:
    #     line = input()
    #     if line.strip() == "":
    #         break
    #     lines.append(line)
    # email_body = "\n".join(lines).strip()
    email_body = input("Enter the email body: ").strip()

    app = build_graph()
    result = await app.ainvoke({"email_from": email_from, "email_body": email_body})

    print("\n=== FINAL RESULT ===")
    print("ok:", result.get("ok"))
    print("message:", result.get("message"))


if __name__ == "__main__":

    asyncio.run(main())
