from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PaymentCheckResult:
    payment_status: str
    provider_status: str
    raw_reference: str | None = None


class PaymentProvider(Protocol):
    def check_session(self, session: dict) -> PaymentCheckResult:
        ...
