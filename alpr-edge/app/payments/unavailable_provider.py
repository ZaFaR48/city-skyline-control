from __future__ import annotations

from app.payments.interface import PaymentCheckResult


class UnavailablePaymentProvider:
    provider_status = "not_integrated"

    def check_session(self, session: dict) -> PaymentCheckResult:
        del session
        return PaymentCheckResult(payment_status="unknown", provider_status=self.provider_status)
