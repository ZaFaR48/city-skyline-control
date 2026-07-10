from __future__ import annotations

from datetime import datetime, timedelta

from app.config import AppConfig
from app.parking.models import ParkingObservation, SessionStatus, SessionUpdate
from app.parking.repositories import ParkingRepository
from app.parking.tariff import TariffConfig, TariffEngine
from app.parking.validators import ensure_utc, normalize_plate
from app.payments.interface import PaymentProvider
from app.payments.unavailable_provider import UnavailablePaymentProvider


class ParkingSessionEngine:
    def __init__(
        self,
        config: AppConfig,
        repository: ParkingRepository,
        payment_provider: PaymentProvider | None = None,
    ) -> None:
        self.config = config
        self.repository = repository
        self.payment_provider = payment_provider or UnavailablePaymentProvider()
        self.tariff = TariffEngine(
            TariffConfig(
                timezone_name=config.parking_timezone,
                start_time=config.parking_start_time,
                end_time=config.parking_end_time,
                free_minutes=config.parking_free_minutes,
                rate_tjs_per_hour=config.parking_rate_tjs_per_hour,
                rounding_mode=config.parking_rounding_mode,
            )
        )

    def process_observation(self, observation: ParkingObservation) -> SessionUpdate:
        observed_at = ensure_utc(observation.observed_at)
        plate = normalize_plate(observation.plate_text)
        existing = self.repository.find_open_session(observation.slot_id, plate)
        if existing is None:
            session = self._create_candidate(observation, observed_at, plate)
            self._add_observation(session["session_id"], observation, observed_at, plate)
            return SessionUpdate(session=session, confirmed=False, created=True)

        self._add_observation(existing["session_id"], observation, observed_at, plate)
        observation_count = int(existing["observation_count"]) + 1
        updates = {
            "last_seen_at": observed_at.isoformat(),
            "latest_frame_path": observation.frame_path,
            "plate_crop_path": observation.plate_crop_path or existing["plate_crop_path"],
            "plate_confidence": max(float(existing["plate_confidence"]), observation.plate_confidence),
            "observation_count": observation_count,
            "exit_miss_count": 0,
        }
        status = existing["session_status"]
        confirmed = existing["confirmed_at"] is not None
        if not confirmed and self._confirmation_met(existing, observed_at, observation_count):
            confirmed = True
            updates["confirmed_at"] = observed_at.isoformat()
            status = self._active_status(existing["first_seen_at"], observed_at)
        elif confirmed:
            status = self._active_status(existing["first_seen_at"], observed_at)

        updates |= self._billing_updates(existing["first_seen_at"], observed_at)
        payment = self.payment_provider.check_session(existing | updates)
        self.repository.add_payment_check(existing["session_id"], payment.provider_status, payment.payment_status, payment.raw_reference)
        if payment.provider_status == "not_integrated":
            updates["payment_status"] = "not_integrated"
            if status == SessionStatus.ACTIVE_BILLABLE:
                status = SessionStatus.NEEDS_REVIEW
        elif payment.payment_status == "paid":
            updates["payment_status"] = "paid"
            status = SessionStatus.PAID
        elif payment.payment_status == "unpaid":
            updates["payment_status"] = "unpaid"
            status = SessionStatus.UNPAID
        else:
            updates["payment_status"] = "unknown"
        updates["session_status"] = status.value if isinstance(status, SessionStatus) else status
        session = self.repository.update_session(existing["session_id"], updates)
        return SessionUpdate(session=session, confirmed=confirmed, created=False)

    def process_slot_missing(self, slot_id: str, observed_at: datetime) -> list[dict]:
        observed_at = ensure_utc(observed_at)
        changed = []
        for session in self.repository.list_active_sessions():
            if session["slot_id"] != slot_id or session["session_status"] in {"candidate", "closed", "cancelled"}:
                continue
            miss_count = int(session["exit_miss_count"]) + 1
            updates = {"exit_miss_count": miss_count}
            last_seen = datetime.fromisoformat(session["last_seen_at"])
            if miss_count >= self.config.session_exit_misses and (
                observed_at - ensure_utc(last_seen)
            ) >= timedelta(seconds=self.config.session_exit_timeout_seconds):
                updates["session_status"] = "closed"
                updates["exited_at"] = observed_at.isoformat()
            else:
                updates["session_status"] = "exit_pending"
            changed.append(self.repository.update_session(session["session_id"], updates))
        return changed

    def refresh_billing(self, now: datetime) -> list[dict]:
        now = ensure_utc(now)
        changed = []
        for session in self.repository.list_active_sessions():
            if session["confirmed_at"] is None or session["session_status"] in {"closed", "cancelled"}:
                continue
            updates = self._billing_updates(session["first_seen_at"], now)
            if session["payment_status"] == "not_integrated" and updates["amount_tjs"] > 0:
                updates["session_status"] = "needs_review"
            else:
                updates["session_status"] = self._active_status(session["first_seen_at"], now).value
            changed.append(self.repository.update_session(session["session_id"], updates))
        return changed

    def _create_candidate(self, observation: ParkingObservation, observed_at: datetime, plate: str) -> dict:
        free_until = self.tariff.free_until(observed_at)
        return self.repository.create_candidate(
            {
                "station_code": observation.station_code,
                "camera_id": observation.camera_id,
                "preset_id": observation.preset_id,
                "zone_id": observation.zone_id,
                "slot_id": observation.slot_id,
                "slot_code": observation.slot_code,
                "zone_type": observation.zone_type,
                "plate_text": plate,
                "plate_confidence": observation.plate_confidence,
                "first_seen_at": observed_at.isoformat(),
                "confirmed_at": None,
                "last_seen_at": observed_at.isoformat(),
                "exited_at": None,
                "free_until": free_until.isoformat(),
                "first_frame_path": observation.frame_path,
                "latest_frame_path": observation.frame_path,
                "plate_crop_path": observation.plate_crop_path,
                "model_version": observation.model_version,
            }
        )

    def _add_observation(self, session_id: str, observation: ParkingObservation, observed_at: datetime, plate: str) -> None:
        self.repository.add_observation(
            session_id,
            {
                "station_code": observation.station_code,
                "camera_id": observation.camera_id,
                "preset_id": observation.preset_id,
                "zone_id": observation.zone_id,
                "slot_id": observation.slot_id,
                "slot_code": observation.slot_code,
                "plate_text": plate,
                "plate_confidence": observation.plate_confidence,
                "observed_at": observed_at.isoformat(),
                "frame_path": observation.frame_path,
                "plate_crop_path": observation.plate_crop_path,
                "model_version": observation.model_version,
            },
        )

    def _confirmation_met(self, session: dict, observed_at: datetime, observation_count: int) -> bool:
        first_seen = ensure_utc(datetime.fromisoformat(session["first_seen_at"]))
        if observed_at - first_seen > timedelta(seconds=self.config.session_confirmation_window_seconds):
            return False
        return observation_count >= self.config.session_confirmation_observations

    def _active_status(self, first_seen_at: str, now: datetime) -> SessionStatus:
        amount = self.tariff.amount_tjs(datetime.fromisoformat(first_seen_at), now)
        return SessionStatus.ACTIVE_BILLABLE if amount > 0 else SessionStatus.ACTIVE_FREE

    def _billing_updates(self, first_seen_at: str, now: datetime) -> dict:
        first_seen = datetime.fromisoformat(first_seen_at)
        return {
            "billable_seconds": self.tariff.billable_seconds(first_seen, now),
            "amount_tjs": self.tariff.amount_tjs(first_seen, now),
        }
