from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from shared.model_schema import LeaveRequest

parser = JsonOutputParser(pydantic_object=LeaveRequest)

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Extract leave request details from emails. Return ONLY valid JSON."),
        ("human", "From: {email_from}\n\nEmail:\n{email_body}\n\n{format_instructions}"),
    ]
).partial(format_instructions=parser.get_format_instructions())


async def extract_leave_request_llm(email_from: str, email_body: str) -> LeaveRequest:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    chain = prompt | llm | parser

    data= await chain.ainvoke({"email_from": email_from, "email_body": email_body})

    if isinstance(data, dict):
        return LeaveRequest(**data)

    if isinstance(data, LeaveRequest):
        return data

    return LeaveRequest(**dict(data))
