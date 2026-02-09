from pydantic import BaseModel, Field, EmailStr
from datetime import date


class LeaveRequest(BaseModel):
    employee_email: EmailStr
    employee_name: str | None = None
    start_date: date
    end_date: date
    reason: str | None = None

class EmployeeStatus(BaseModel):
    employee_email: EmailStr
    active: bool


class LeaveStatus(BaseModel):
    employee_email: EmailStr
    currently_on_leave: bool


class CreateLOAResponse(BaseModel):
    transaction_id: str = Field(..., description="Workday transaction id / reference id")
    status: str = "IN_REVIEW"
