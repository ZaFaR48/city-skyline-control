from __future__ import annotations

from app.alpr.models import NormalizedPlate


LETTER_TO_DIGIT = {"O": "0", "I": "1", "B": "8", "S": "5", "Z": "2", "G": "6", "Q": "0"}
DIGIT_TO_LETTER = {"0": "O", "1": "I", "8": "B", "5": "S", "2": "Z", "6": "G"}


class TajikPlateNormalizer:
    def normalize(self, raw_text: str) -> NormalizedPlate:
        cleaned = "".join(ch for ch in raw_text.upper() if ch.isalnum())
        candidates = self._candidates(cleaned)
        best = max(candidates, key=lambda item: item[1])
        canonical, score, changes = best
        display = canonical
        if len(canonical) == 8:
            display = f"{canonical[:4]} {canonical[4:6]} {canonical[6:]}"
        return NormalizedPlate(
            raw_text=raw_text,
            canonical_text=canonical,
            display_text=display,
            normalization_changes=changes,
            normalization_score=score,
        )

    def _candidates(self, value: str) -> list[tuple[str, float, list[str]]]:
        candidates = [(value, self._pattern_score(value), [])]
        if len(value) == 8:
            chars = list(value)
            changes: list[str] = []
            for idx in [0, 1, 2, 3, 6, 7]:
                if chars[idx].isalpha() and chars[idx] in LETTER_TO_DIGIT:
                    before = chars[idx]
                    chars[idx] = LETTER_TO_DIGIT[chars[idx]]
                    changes.append(f"{before}->{chars[idx]} at {idx}")
            for idx in [4, 5]:
                if chars[idx].isdigit() and chars[idx] in DIGIT_TO_LETTER:
                    before = chars[idx]
                    chars[idx] = DIGIT_TO_LETTER[chars[idx]]
                    changes.append(f"{before}->{chars[idx]} at {idx}")
            score = self._pattern_score("".join(chars)) - len(changes) * 0.02
            candidates.append(("".join(chars), score, changes))
        return candidates

    def _pattern_score(self, value: str) -> float:
        if len(value) == 8:
            score = 0.0
            for idx in [0, 1, 2, 3, 6, 7]:
                score += 1.0 if value[idx].isdigit() else 0.0
            for idx in [4, 5]:
                score += 1.0 if value[idx].isalpha() else 0.0
            return score / 8
        return 0.2
