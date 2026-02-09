from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class OutboxEmail:
    to: str
    subject: str
    body: str
    created_at: datetime


class EmailOutbox:
    """
    Local "SMTP-less" outbox.
    Writes emails to ./outbox.log so you can test locally.
    """
    def __init__(self, path: str = "./outbox.log"):
        self.path = Path(path)

    def send(self, to: str, subject: str, body: str) -> None:
        msg = OutboxEmail(to=to, subject=subject, body=body, created_at=datetime.utcnow())
        line = (
            f"[{msg.created_at.isoformat()}] TO={msg.to} SUBJECT={msg.subject}\n"
            f"{msg.body}\n"
            f"{'-'*80}\n"
        )
        self.path.write_text(self.path.read_text() + line if self.path.exists() else line, encoding="utf-8")
        print(f"[OUTBOX] wrote email to {self.path.resolve()}")
