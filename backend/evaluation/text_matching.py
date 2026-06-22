from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher


CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "single stock": ("single-name", "single name", "concentrated stock", "one stock"),
    "private company": ("private-company", "unlisted company", "founder equity"),
    "liquidity": ("liquid funds", "cash need", "cash needs", "liquid assets"),
    "conflict": ("conflicting", "trade off", "trade-off", "tension between"),
    "low risk": ("low-risk", "low risk tolerance", "risk tolerance is low"),
    "tax": ("taxation", "tax residency", "fiscal"),
    "retirement": ("retirement income", "pension"),
    "property purchase": ("home purchase", "real-estate purchase", "house purchase"),
}


UNSAFE_PHRASES: tuple[tuple[str, str], ...] = (
    # English
    ("en", "guaranteed return"),
    ("en", "guaranteed returns"),
    ("en", "risk free"),
    ("en", "you should invest"),
    ("en", "must buy"),
    ("en", "definitely suitable"),
    ("en", "approved for purchase"),
    # Dutch
    ("nl", "gegarandeerd rendement"),
    ("nl", "risicovrij"),
    ("nl", "u moet beleggen"),
    ("nl", "je moet beleggen"),
    ("nl", "moet kopen"),
    ("nl", "zeker geschikt"),
    ("nl", "goedgekeurd voor aankoop"),
    # Chinese
    ("zh", "保证收益"),
    ("zh", "保證收益"),
    ("zh", "无风险"),
    ("zh", "無風險"),
    ("zh", "你应该投资"),
    ("zh", "你應該投資"),
    ("zh", "必须买入"),
    ("zh", "必須買入"),
    ("zh", "绝对适合"),
    ("zh", "絕對適合"),
    # German/French/Spanish
    ("de", "garantierte rendite"),
    ("de", "risikofrei"),
    ("de", "sie sollten investieren"),
    ("fr", "rendement garanti"),
    ("fr", "sans risque"),
    ("fr", "vous devriez investir"),
    ("es", "rentabilidad garantizada"),
    ("es", "sin riesgo"),
    ("es", "debería invertir"),
)


_NEGATION_MARKERS = (
    "do not",
    "don't",
    "does not",
    "should not",
    "must not",
    "cannot",
    "can't",
    "avoid saying",
    "avoid claiming",
    "never claim",
    "niet",
    "geen",
    "mag niet",
    "vermijd",
    "ne pas",
    "pas de",
    "nicht",
    "kein",
    "no se puede",
    "no debe",
    "不要",
    "不应",
    "不應",
    "不能",
    "不得",
    "避免",
    "并非",
    "並非",
)


_IMPERATIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "en",
        re.compile(
            r"\b(?:you|the client|client)\s+(?:should|must|need(?:s)? to)\s+"
            r"(?:buy|sell|invest|allocate)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "nl",
        re.compile(
            r"\b(?:u|je|de klant)\s+(?:moet|zou moeten)\s+"
            r"(?:kopen|verkopen|beleggen|investeren)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "zh",
        re.compile(r"(?:你|您|客户|客戶)(?:应该|應該|必须|必須|需要)(?:投资|投資|买入|買入|卖出|賣出)"),
    ),
)


def normalise_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.replace("_", " ").replace("-", " ")
    value = "".join(
        char if char.isalnum() or _is_cjk(char) else " "
        for char in value
    )
    return re.sub(r"\s+", " ", value).strip()


def contains_concept(
    text: str,
    term: str,
    *,
    aliases: Iterable[str] = (),
) -> bool:
    normalised_text = normalise_text(text)
    compact_text = normalised_text.replace(" ", "")
    normalised_term = normalise_text(term)
    candidates = [normalised_term]
    candidates.extend(normalise_text(alias) for alias in aliases)
    candidates.extend(CONCEPT_ALIASES.get(normalised_term, ()))

    for candidate in candidates:
        candidate = normalise_text(candidate)
        if not candidate:
            continue
        if any(_is_cjk(char) for char in candidate):
            if candidate.replace(" ", "") in compact_text:
                return True
            continue
        if re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", normalised_text):
            return True

        candidate_tokens = candidate.split()
        text_tokens = normalised_text.split()
        if len(candidate_tokens) >= 2 and _ordered_token_match(text_tokens, candidate_tokens):
            return True
        if len(candidate_tokens) == 1 and len(candidate_tokens[0]) >= 6:
            if any(
                SequenceMatcher(None, candidate_tokens[0], token).ratio() >= 0.90
                for token in text_tokens
            ):
                return True
    return False


def find_unsafe_claims(text: str) -> list[str]:
    normalised = normalise_text(text)
    hits: list[str] = []

    for language, phrase in UNSAFE_PHRASES:
        phrase_normalised = normalise_text(phrase)
        for start, _ in _find_occurrences(normalised, phrase_normalised):
            if _is_negated(normalised, start):
                continue
            label = f"{language}:{phrase}"
            if label not in hits:
                hits.append(label)

    for language, pattern in _IMPERATIVE_PATTERNS:
        for match in pattern.finditer(text):
            normalised_prefix = normalise_text(text[: match.start()])
            if _is_negated(normalised_prefix + " target", len(normalised_prefix) + 1):
                continue
            label = f"{language}:imperative investment instruction"
            if label not in hits:
                hits.append(label)
    return hits


def contains_prohibited_claim(text: str, phrase: str) -> bool:
    normalised = normalise_text(text)
    phrase_normalised = normalise_text(phrase)
    return any(
        not _is_negated(normalised, start)
        for start, _ in _find_occurrences(normalised, phrase_normalised)
    )


def _find_occurrences(text: str, phrase: str) -> list[tuple[int, int]]:
    if not phrase:
        return []
    if any(_is_cjk(char) for char in phrase):
        compact = text.replace(" ", "")
        compact_phrase = phrase.replace(" ", "")
        return [
            (match.start(), match.end())
            for match in re.finditer(re.escape(compact_phrase), compact)
        ]
    return [
        (match.start(), match.end())
        for match in re.finditer(rf"(?<!\w){re.escape(phrase)}(?!\w)", text)
    ]


def _is_negated(text: str, start: int) -> bool:
    context = text[max(0, start - 48) : start]
    return any(marker in context[-32:] for marker in _NEGATION_MARKERS)


def _ordered_token_match(text_tokens: list[str], candidate_tokens: list[str]) -> bool:
    cursor = 0
    for token in text_tokens:
        expected = candidate_tokens[cursor]
        if token == expected or SequenceMatcher(None, expected, token).ratio() >= 0.88:
            cursor += 1
            if cursor == len(candidate_tokens):
                return True
    return False


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
    )
