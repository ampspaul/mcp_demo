import httpx
from shared.model_schema import EmployeeStatus, LeaveStatus, CreateLOAResponse, LeaveRequest


class WorkdayClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def get_employee_status(self, employee_email: str) -> EmployeeStatus:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/employees/status", params={"email": employee_email})
            r.raise_for_status()
            return EmployeeStatus(**r.json())

    async def get_leave_status(self, employee_email: str) -> LeaveStatus:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/employees/leave-status", params={"email": employee_email})
            r.raise_for_status()
            return LeaveStatus(**r.json())

    async def create_loa(self, req: LeaveRequest) -> CreateLOAResponse:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{self.base_url}/loa", json=req.model_dump(mode="json"))
            r.raise_for_status()
            return CreateLOAResponse(**r.json())
