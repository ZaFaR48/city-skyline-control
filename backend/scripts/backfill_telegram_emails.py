from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models import AuditLog, AuditSource, User


OLD_SUFFIX = "@telegram.invalid"
NEW_SUFFIX = "@telegram.cityparking.tj"


@dataclass
class Finding:
    user_id: int
    username: str
    old_email: str
    proposed_email: str
    status: str
    reason: str | None = None


async def backfill_telegram_emails(db: AsyncSession, *, apply: bool) -> list[Finding]:
    users = (
        await db.execute(select(User).where(User.email.endswith(OLD_SUFFIX)).order_by(User.id))
    ).scalars().all()
    findings: list[Finding] = []
    for user in users:
        target = f"{user.username}{NEW_SUFFIX}"
        conflict = (
            await db.execute(select(User.id).where(User.email == target, User.id != user.id))
        ).scalar_one_or_none()
        if conflict:
            findings.append(Finding(user.id, user.username, user.email, target, "skipped", f"email conflict with user {conflict}"))
            continue
        status = "applied" if apply else "would_apply"
        findings.append(Finding(user.id, user.username, user.email, target, status))
        if apply:
            before = user.email
            user.email = target
            db.add(
                AuditLog(
                    actor_user_id=None,
                    action="user.telegram_email_backfill",
                    entity_type="user",
                    entity_id=str(user.id),
                    before_data={"email": before},
                    after_data={"email": target},
                    source=AuditSource.system.value,
                )
            )
    if apply:
        await db.commit()
    return findings


def write_report(findings: list[Finding], *, apply: bool, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": "apply" if apply else "dry-run",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "scanned": len(findings),
            "eligible": sum(item.status in {"would_apply", "applied"} for item in findings),
            "skipped": sum(item.status == "skipped" for item in findings),
        },
        "findings": [asdict(item) for item in findings],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Safely replace invalid Telegram placeholder emails")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = args.report or Path("../tmp") / f"telegram-email-backfill-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    async with SessionLocal() as db:
        findings = await backfill_telegram_emails(db, apply=args.apply)
    write_report(findings, apply=args.apply, path=report)
    print(f"mode={'apply' if args.apply else 'dry-run'}")
    print(f"findings={len(findings)} eligible={sum(item.status in {'would_apply', 'applied'} for item in findings)} skipped={sum(item.status == 'skipped' for item in findings)}")
    print(f"report={report.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
