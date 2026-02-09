import re
from datetime import date
from shared.model_schema import LeaveRequest


_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _parse_date(s: str) -> date:
    # expects YYYY-MM-DD
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def extract_leave_request(email_from: str, email_body: str) -> LeaveRequest:
    """
    Very small demo extractor:
    - finds 2 dates in YYYY-MM-DD format
    - tries to find a name from 'Name:'
    - reason from 'Reason:'
    """
    dates = _DATE_RE.findall(email_body)
    if len(dates) < 2:
        raise ValueError("Could not find start/end dates in YYYY-MM-DD format in email body.")

    name = None
    m_name = re.search(r"Name:\s*(.+)", email_body, re.IGNORECASE)
    if m_name:
        name = m_name.group(1).strip()

    reason = None
    m_reason = re.search(r"Reason:\s*(.+)", email_body, re.IGNORECASE)
    if m_reason:
        reason = m_reason.group(1).strip()

    return LeaveRequest(
        employee_email=email_from,
        employee_name=name,
        start_date=_parse_date(dates[0]),
        end_date=_parse_date(dates[1]),
        reason=reason,
    )
