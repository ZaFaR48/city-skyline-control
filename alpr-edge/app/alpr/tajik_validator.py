from __future__ import annotations

import re

from app.alpr.models import PlateValidation


DEFAULT_REGION_CODES = {
    "01",
    "02",
    "03",
    "04",
    "05",
    "07",
    "08",
    "09",
}


class TajikPlateValidator:
    def __init__(self, region_codes: set[str] | None = None) -> None:
        self.region_codes = region_codes or DEFAULT_REGION_CODES
        self.rules = {
            "private_standard": re.compile(r"^\d{4}[A-Z]{2}\d{2}$"),
            "public_transport": re.compile(r"^\d{3}[A-Z]{3}\d{2}$"),
            "trailer": re.compile(r"^\d{4}[A-Z]\d{2}$"),
            "motorcycle": re.compile(r"^\d{3}[A-Z]{2}\d{2}$"),
            "diplomatic": re.compile(r"^D\d{5,7}$"),
            "government": re.compile(r"^[A-Z]{2}\d{4}\d{2}$"),
            "special": re.compile(r"^(?:TJ|SP)[A-Z0-9]{4,8}$"),
        }

    def validate(self, canonical_text: str) -> PlateValidation:
        warnings: list[str] = []
        for name, pattern in self.rules.items():
            if not pattern.match(canonical_text):
                continue
            region = canonical_text[-2:] if len(canonical_text) >= 2 and canonical_text[-2:].isdigit() else None
            if region and region not in self.region_codes:
                warnings.append("region_code_unconfirmed")
                return PlateValidation(canonical_text, name, "needs_review", region, warnings)
            status = "accepted" if name == "private_standard" else "needs_review"
            return PlateValidation(canonical_text, name, status, region, warnings)
        return PlateValidation(canonical_text, "unknown", "needs_review", None, ["unknown_format"])
