from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

load_dotenv()

class IntentOut(BaseModel):
    intent: Literal["balance", "create_loa", "unknown"] = Field(
        description="User intent. Use 'balance' for questions about leave balance. "
                    "Use 'create_loa' for requests to create/apply/request leave. "
                    "Use 'unknown' if unclear."
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


prompt = ChatPromptTemplate.from_messages(
    [
        ("system",
         "You are an intent classifier for an HR Leave assistant.\n"
         "Return JSON matching the schema.\n"
         "Rules:\n"
         "- balance: user asks remaining leave days, leave balance, PTO balance.\n"
         "- create_loa: user asks to create/apply/request leave of absence, provides dates or asks to take leave.\n"
         "- unknown: greetings, unrelated, or unclear.\n"
         "Be strict: choose only one intent."),
        ("human", "Thread id (employee email): {email_from}\nUser message: {text}"),
    ]
)

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
)


async def classify_intent_llm(email_from: str, text: str) -> IntentOut:
    # structured output is the cleanest (no JSON parsing headaches)
    chain = prompt | llm.with_structured_output(IntentOut)
    res= await chain.ainvoke({"email_from": email_from, "text": text})
    return res







