from fastapi import FastAPI, HTTPException
from shared.model_schema import LeaveRequest, EmployeeStatus, LeaveStatus, CreateLOAResponse
from uuid import uuid4

app = FastAPI(title="Mock Workday API", version="0.1.0")

# In-memory "database"
EMPLOYEES = {
    "alice@company.com": {"active": True, "on_leave": False},
    "bob@company.com": {"active": True, "on_leave": True},
    "inactive@company.com": {"active": False, "on_leave": False},
}


@app.get("/employees/status", response_model=EmployeeStatus)
def employee_status(email: str):
    row = EMPLOYEES.get(email)
    if not row:
        # unknown employees treated as inactive for demo
        return EmployeeStatus(employee_email=email, active=False)
    return EmployeeStatus(employee_email=email, active=bool(row["active"]))


@app.get("/employees/leave-status", response_model=LeaveStatus)
def leave_status(email: str):
    row = EMPLOYEES.get(email)
    if not row:
        return LeaveStatus(employee_email=email, currently_on_leave=False)
    return LeaveStatus(employee_email=email, currently_on_leave=bool(row["on_leave"]))


@app.post("/loa", response_model=CreateLOAResponse)
def create_loa(req: LeaveRequest):
    row = EMPLOYEES.get(req.employee_email)
    if not row or not row["active"]:
        raise HTTPException(status_code=400, detail="Employee not active.")
    if row["on_leave"]:
        raise HTTPException(status_code=400, detail="Employee already on leave.")

    # Create "transaction"
    txn = f"LOA-{uuid4().hex[:10].upper()}"
    # mark as on leave for demo
    row["on_leave"] = True

    return CreateLOAResponse(transaction_id=txn, status="IN_REVIEW")
