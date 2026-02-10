

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

FAILURE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are an HR leave assistant. Write concise, professional messages. "
     "If leave cannot be created, explain the reason clearly and provide next steps. "
     "Do NOT mention internal flags or JSON. Use a friendly tone. Keep it under 120 words."),
    ("human",
     "Employee email: {employee_email}\n"
     "Employee name: {employee_name}\n"
     "Requested dates: {start_date} to {end_date}\n"
     "Reason (optional): {reason}\n"
     "Validation:\n"
     "- Active employee: {active}\n"
     "- Currently on leave: {currently_on_leave}\n"
     "- Leave balance days: {balance_days}\n"
     "Create a message to the employee explaining why the LOA was not created and what to do next."
     )
])


async def friendly_message_lln(prompt_vars) -> str:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    llm_msg = await llm.ainvoke(FAILURE_PROMPT.format_messages(**prompt_vars))
    friendly_text = llm_msg.content.strip()
    return friendly_text