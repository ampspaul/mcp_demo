
import asyncio
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from agent_app.nodes import (
    AgentState,node_extract,node_validate,node_balance,node_create_loa,
    node_email_success,node_email_failure,
    node_reply_balance,
    route_after_intent,
    node_route_intent,
    route_after_balance,
    route_after_create_loa
    )

from langgraph.checkpoint.memory import InMemorySaver

load_dotenv() 

def build_graph(checkpointer):
    g = StateGraph(AgentState)
    #Nodes 
    g.add_node("route_intent", node_route_intent)
    g.add_node("extract", node_extract)
    g.add_node("validate", node_validate)
    g.add_node("balance", node_balance)
    g.add_node("reply_balance", node_reply_balance)
    g.add_node("create_loa", node_create_loa)
    g.add_node("email_success", node_email_success)
    g.add_node("email_failure", node_email_failure)

    #Edges 
    g.set_entry_point("route_intent")
    g.add_conditional_edges(
        "route_intent",
        route_after_intent,
        {"validate": "validate", "extract": "extract", "email_failure": "email_failure"},
    )

    g.add_edge("extract", "validate")
    g.add_edge("validate", "balance")
    g.add_conditional_edges(
        "balance",
        route_after_balance,
        {"reply_balance": "reply_balance", "create_loa": "create_loa", "email_failure": "email_failure"},
    )
    g.add_edge("reply_balance", END)
    g.add_conditional_edges(
        "create_loa",
        route_after_create_loa,
        {"email_success": "email_success", "email_failure": "email_failure"},
    )
    g.add_edge("email_success", END)
    g.add_edge("email_failure", END)
    return g.compile(checkpointer=checkpointer)


async def main():
    checkpointer = InMemorySaver()
    app = build_graph(checkpointer)

    thread_id = input("Thread id (ex: amps@company.com): ").strip()

    while True:
        message = input("Enter the your message: ").strip()
        if message.lower() in ("quite" ,"exit"):
            break
        email_from=thread_id
        result = await app.ainvoke(
            {"email_from": email_from, "email_body": message},
           config={"configurable": {"thread_id": thread_id}},)
        print("\n=== FINAL RESULT ===",result)
        print("ok:", result.get("ok"))
        print("message:", result.get("message"))
    


if __name__ == "__main__":
    asyncio.run(main())
