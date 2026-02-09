import asyncio
import aiosqlite
from fastmcp import FastMCP

from shared.settings import settings
from shared.workday_client import WorkdayClient
from shared.model_schema import LeaveRequest

mcp = FastMCP(name="loa-mcp-server")


async def init_db():
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS leave_balance (
              employee_email TEXT PRIMARY KEY,
              balance_days INTEGER NOT NULL
            )
            """
        )
        await db.execute(
            "INSERT OR IGNORE INTO leave_balance(employee_email, balance_days) VALUES (?, ?)",
            ("alice@company.com", 12),
        )
        await db.execute(
            "INSERT OR IGNORE INTO leave_balance(employee_email, balance_days) VALUES (?, ?)",
            ("bob@company.com", 3),
        )
        await db.commit()


@mcp.tool
async def validate_employee(employee_email: str) -> dict:
    client = WorkdayClient(settings.workday_api_base_url)
    status = await client.get_employee_status(employee_email)
    leave = await client.get_leave_status(employee_email)
    return {
        "employee_email": employee_email,
        "active": status.active,
        "currently_on_leave": leave.currently_on_leave,
        "ok_to_create_loa": status.active and (not leave.currently_on_leave),
    }


@mcp.tool
async def get_leave_balance(employee_email: str) -> dict:
    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(
            "SELECT balance_days FROM leave_balance WHERE employee_email = ?",
            (employee_email,),
        ) as cur:
            row = await cur.fetchone()

    return {
        "employee_email": employee_email,
        "balance_days": int(row[0]) if row else 0,
    }


@mcp.tool
async def create_loa(employee_email: str, start_date: str, end_date: str, employee_name: str | None = None, reason: str | None = None) -> dict:
    """
    REST tool: calls Workday LOA endpoint (mock for now)
    Dates must be YYYY-MM-DD
    """
    from datetime import date
    from shared.workday_client import WorkdayClient
    from shared.settings import settings

    # convert strings to LeaveRequest
    y1, m1, d1 = map(int, start_date.split("-"))
    y2, m2, d2 = map(int, end_date.split("-"))

    req = LeaveRequest(
        employee_email=employee_email,
        employee_name=employee_name,
        start_date=date(y1, m1, d1),
        end_date=date(y2, m2, d2),
        reason=reason,
    )

    client = WorkdayClient(settings.workday_api_base_url)
    resp = await client.create_loa(req)

    return {"transaction_id": resp.transaction_id, "status": resp.status}


def main():
    asyncio.run(init_db())
    mcp.run(
        transport="sse",
        host="127.0.0.1",
        port=9002,
        path="/sse",
    )


if __name__ == "__main__":
    main()
