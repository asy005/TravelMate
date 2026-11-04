from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

_POSITIVE_WORDS: frozenset[str] = frozenset({
    "good", "great", "excellent", "amazing", "wonderful", "fantastic",
    "superb", "awesome", "outstanding", "perfect", "best", "top", "loved",
    "love", "like", "liked", "enjoy", "enjoyed", "pleasant", "pleasing",
    "pleased", "happy", "happiness", "satisfied", "satisfaction", "delighted",
    "delight", "nice", "beautiful", "stunning", "gorgeous", "brilliant",
    "spectacular", "exceptional", "flawless", "smooth", "comfortable",
    "clean", "spacious", "friendly", "helpful", "polite", "attentive",
    "professional", "efficient", "recommend", "recommended", "worth",
    "convenient", "easy", "seamless", "memorable", "charming", "cozy",
    "cosy", "welcoming", "warm", "fresh", "tasty", "delicious", "fabulous",
    "incredible", "impressive", "magnificent", "breathtaking", "peaceful",
    "relaxing", "relaxed", "serene", "lovely", "fun", "exciting",
    "adventure", "adventurous", "unique", "special", "comfortable",
    "affordable", "value", "bargain",
})

_NEGATIVE_WORDS: frozenset[str] = frozenset({
    "bad", "terrible", "awful", "horrible", "poor", "worst", "disappointing",
    "disappointed", "disappoints", "disappoint", "unpleasant", "disgusting",
    "dirty", "messy", "noisy", "rude", "unhelpful", "unfriendly",
    "unprofessional", "slow", "broken", "damaged", "overpriced", "expensive",
    "waste", "wasted", "regret", "avoid", "never", "refund", "complaint",
    "complain", "problem", "issue", "bug", "fault", "defect", "failure",
    "fail", "failed", "cancel", "cancelled", "canceled", "delay", "delayed",
    "late", "lost", "missing", "uncomfortable", "cramped", "smelly",
    "stained", "leaking", "flooded", "dark", "cold", "hot", "sweaty",
    "crowded", "overrated", "mediocre", "below", "substandard", "lacking",
    "inadequate", "insufficient", "disappointing", "misleading", "fake",
    "scam", "fraud", "cheated", "boring", "dull", "bland", "tasteless",
    "inedible", "stale", "horrible", "nasty", "unclean", "unsafe",
    "dangerous", "hazardous",
})

_NEGATION_WORDS: frozenset[str] = frozenset({
    "not", "no", "never", "neither", "nor", "nothing", "without",
    "hardly", "barely", "scarcely", "don't", "didn't", "doesn't",
    "wasn't", "weren't", "isn't", "aren't", "can't", "won't", "wouldn't",
    "shouldn't", "couldn't", "haven't", "hasn't", "hadn't",
})

_INTENSIFIER_WORDS: frozenset[str] = frozenset({
    "very", "extremely", "absolutely", "completely", "totally", "utterly",
    "incredibly", "highly", "truly", "really", "so", "super",
    "exceptionally", "remarkably",
})

_POSITIVE_THRESHOLD = 0.05
_NEGATIVE_THRESHOLD = -0.05
_NEGATION_WINDOW = 3

@dataclass(frozen=True)
class SentimentResult:
    label: str
    score: float
    token_count: int

def _tokenise(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    return re.findall(r"[a-z']+", text)

def _soft_clamp(raw: float, token_count: int) -> float:
    if token_count == 0:
        return 0.0
    normalised = raw / max(token_count, 1)
    return max(-1.0, min(1.0, normalised))

def analyse(text: Optional[str]) -> SentimentResult:
    if not text or not text.strip():
        return SentimentResult(label="neutral", score=0.0, token_count=0)
    tokens = _tokenise(text)
    raw_score = 0.0
    scored_token_count = 0
    negated_window = 0
    intensify = 1.0

    for i, token in enumerate(tokens):
        if negated_window > 0:
            negated_window -= 1

        if token in _NEGATION_WORDS:
            negated_window = _NEGATION_WINDOW
            continue

        if token in _INTENSIFIER_WORDS:
            intensify = 1.5
            continue

        valence = 0.0
        if token in _POSITIVE_WORDS:
            valence = +1.0
        elif token in _NEGATIVE_WORDS:
            valence = -1.0

        if valence != 0.0:
            if negated_window > 0:
                valence = -valence
            raw_score += valence * intensify
            scored_token_count += 1

        if token not in _INTENSIFIER_WORDS:
            intensify = 1.0

    compound = _soft_clamp(raw_score, max(scored_token_count, 1))

    if compound >= _POSITIVE_THRESHOLD:
        label = "positive"
    elif compound <= _NEGATIVE_THRESHOLD:
        label = "negative"
    else:
        label = "neutral"

    return SentimentResult(label=label, score=round(compound, 4), token_count=scored_token_count)

def classify_by_rating(rating: float) -> SentimentResult:
    score = round(max(-1.0, min(1.0, (rating - 3.0) / 2.0)), 4)
    if rating >= 4.0:
        label = "positive"
    elif rating >= 3.0:
        label = "neutral"
    else:
        label = "negative"
    return SentimentResult(label=label, score=score, token_count=0)

def classify_review(text: Optional[str], rating: Optional[float] = None) -> SentimentResult:
    result = analyse(text)
    if result.token_count == 0 and rating is not None:
        return classify_by_rating(rating)
    return result

_NEGATION_PREFIX_PATTERN = re.compile(
    r"\b(?:not|never|no|hardly|barely|scarcely|without|wasn't|was\s+not|weren't|were\s+not|isn't|is\s+not|aren't|are\s+not|don't|doesn't|didn't|won't|wouldn't|neither|nor)\s+(?:very\s+|extremely\s+|at\s+all\s+|too\s+|that\s+|particularly\s+|especially\s+)?$",
    re.IGNORECASE,
)

def _is_negated(text: str, match_start: int, window: int = 50) -> bool:
    prefix = text[max(0, match_start - window):match_start]
    tokens = prefix.strip().split()
    if not tokens:
        return False
    trailing = " ".join(tokens[-4:]) + " "
    return bool(_NEGATION_PREFIX_PATTERN.search(trailing))

_ASPECT_PRAISE_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "Helpful & courteous staff",
        [
            r"\bstaff\b.{0,30}\b(?:helpful|friendly|polite|attentive|courteous|welcoming|kind|cooperative)\b",
            r"\b(?:helpful|friendly|polite|attentive|courteous|welcoming|kind|cooperative)\b.{0,30}\bstaff\b",
        ],
    ),
    (
        "Comfort & convenience",
        [
            r"\b(?:very\s+|extremely\s+|super\s+)?comfortable\b",
            r"\bconvenient\s+(?:location|stay|access)\b",
            r"\bcomfortable\s+and\s+convenient\b",
            r"\bcozy\b",
            r"\bcosy\b",
            r"\bspacious\s+(?:room|rooms|stay|hotel)\b",
        ],
    ),
    (
        "Great value for money",
        [
            r"\bvalue for money\b",
            r"\bgreat value\b",
            r"\bgood value\b",
            r"\baffordable\b",
            r"\bbargain\b",
            r"\bworth (?:the money|every penny|it|the price|staying|visiting)\b",
            r"\bwell worth\b",
        ],
    ),
    (
        "Smooth & seamless experience",
        [
            r"\bsmooth experience\b",
            r"\bfrom start to finish\b",
            r"\bseamless\b",
            r"\bwell organized\b",
            r"\bwell-organized\b",
        ],
    ),
    (
        "Family-friendly environment",
        [
            r"\bwhole family\b",
            r"\bfamily\s+(?:had a|trip|vacation|stay|loved|enjoyed)\b",
            r"\bfamily-friendly\b",
            r"\bgreat for (?:kids|families|family)\b",
        ],
    ),
    (
        "Cleanliness & hygiene",
        [
            r"\b(?:very\s+|extremely\s+|super\s+)?clean\s+(?:room|rooms|hotel|place|bathroom|environment|premises)\b",
            r"\bspotless\b",
            r"\bclean and (?:tidy|comfortable|fresh|hygienic)\b",
            r"\bmaintained\s+cleanliness\b",
            r"\bsparkling clean\b",
        ],
    ),
    (
        "Scenic views & peaceful ambience",
        [
            r"\bpeaceful\s+(?:ambience|atmosphere|surroundings|stay|environment)\b",
            r"\bpeaceful\b",
            r"\bserene\b",
            r"\brelaxing\s+(?:ambience|atmosphere|stay|vibe)\b",
            r"\b(?:valley|lake|mountain|scenic|ocean|sea|river)\s+view\b",
            r"\bbeautiful view\b",
            r"\bbreathtaking\b",
        ],
    ),
    (
        "Delicious food & dining",
        [
            r"\bdelicious\s+(?:food|breakfast|meal|dinner|cuisine|dishes)\b",
            r"\bdelicious\b",
            r"\btasty\s+(?:food|breakfast|meal|dinner|cuisine)\b",
            r"\bgreat food\b",
            r"\bgood food\b",
            r"\bgreat breakfast\b",
            r"\bexcellent food\b",
        ],
    ),
]

_ASPECT_COMPLAINT_PATTERNS: list[tuple[str, list[str]]] = [
    (
        "Cleanliness & hygiene issues",
        [
            r"\bissues? with cleanliness\b",
            r"\bcleanliness.*(?:issue|problem|poor|bad|needs? improvement)\b",
            r"\bdirty\b",
            r"\bunclean\b",
            r"\bsmelly\b",
            r"\bstained\b",
            r"\bnot clean\b",
            r"\bunhygienic\b",
            r"\bfilthy\b",
        ],
    ),
    (
        "Service & response delays",
        [
            r"\bresponse time could be better\b",
            r"\bissues? with.*service\b",
            r"\bslow service\b",
            r"\bslow response\b",
            r"\brude staff\b",
            r"\bpoor service\b",
            r"\bunhelpful staff\b",
            r"\bunfriendly staff\b",
            r"\bunprofessional\b",
            r"\bhorrible service\b",
            r"\bterrible service\b",
        ],
    ),
    (
        "Mismatch with expectations",
        [
            r"\bdid not match what was promised\b",
            r"\bnot match what was promised\b",
            r"\bdoes not match what was promised\b",
            r"\bmisleading\b",
            r"\bnot as described\b",
            r"\bnot as advertised\b",
            r"\bdisappointed with\b",
            r"\bexperience did not match\b",
        ],
    ),
    (
        "Overall dissatisfaction",
        [
            r"\bwould not recommend\b",
            r"\bnot satisfied\b",
            r"\bworst\b",
            r"\bterrible stay\b",
            r"\bterrible experience\b",
            r"\bhorrible experience\b",
            r"\bawful experience\b",
        ],
    ),
    (
        "Requires general improvement",
        [
            r"\bneeds? improvement\b",
            r"\bthings could be improved\b",
            r"\bcould be better\b",
            r"\baverage experience\b",
            r"\bbelow expectations\b",
        ],
    ),
    (
        "Overpriced / poor value",
        [
            r"\boverpriced\b",
            r"\bexpensive\b",
            r"\bwaste of money\b",
            r"\bnot worth\b",
            r"\bpoor value\b",
            r"\bnot value for money\b",
        ],
    ),
    (
        "Noise disturbance",
        [
            r"\bnoisy\b",
            r"\bloud noise\b",
            r"\bnoise disturbance\b",
            r"\btoo loud\b",
        ],
    ),
]

def extract_aspects_and_complaints(
    texts: list[str],
) -> tuple[list[str], list[str]]:
    import collections
    praises: collections.Counter[str] = collections.Counter()
    complaints: collections.Counter[str] = collections.Counter()

    for raw in texts:
        if not raw or not isinstance(raw, str):
            continue
        lower = raw.lower()

        complaints_in_review: set[str] = set()
        for label, patterns in _ASPECT_COMPLAINT_PATTERNS:
            matched = False
            for p in patterns:
                for m in re.finditer(p, lower):
                    matched_str = m.group(0)
                    if not re.match(r"^(?:not|did\s+not|does\s+not|is\s+not|was\s+not|un)\b", matched_str):
                        if _is_negated(lower, m.start()):
                            continue
                    if any(fp in lower for fp in ("no issues with", "no complaints", "no problem")):
                        if "issues" in matched_str or "problem" in matched_str or "complaint" in matched_str:
                            continue

                    complaints[label] += 1
                    complaints_in_review.add(label)
                    matched = True
                    break
                if matched:
                    break

        for label, patterns in _ASPECT_PRAISE_PATTERNS:
            if label == "Cleanliness & hygiene" and "Cleanliness & hygiene issues" in complaints_in_review:
                continue
            if label == "Helpful & courteous staff" and "Service & response delays" in complaints_in_review:
                continue
            if label == "Great value for money" and "Overpriced / poor value" in complaints_in_review:
                continue

            matched = False
            for p in patterns:
                for m in re.finditer(p, lower):
                    if _is_negated(lower, m.start()):
                        continue
                    praises[label] += 1
                    matched = True
                    break
                if matched:
                    break

    praised_list = [label for label, _ in praises.most_common(5)]
    complaints_list = [label for label, _ in complaints.most_common(5)]
    return praised_list, complaints_list

def generate_sentiment_summary(
    total: int,
    pos: int,
    neu: int,
    neg: int,
) -> Optional[str]:
    if total == 0:
        return None
    pos_pct = round(pos / total * 100, 1)
    neg_pct = round(neg / total * 100, 1)

    if pos_pct >= 80:
        return f"Overwhelmingly positive feedback ({pos_pct}% positive across {total} review{'s' if total != 1 else ''})."
    elif pos_pct >= 60:
        return f"Mostly positive guest feedback ({pos_pct}% positive across {total} review{'s' if total != 1 else ''})."
    elif pos_pct >= 40:
        return f"Mixed guest sentiment with both positive points and areas for improvement ({pos_pct}% positive, {neg_pct}% negative)."
    elif neg_pct >= 50:
        return f"Critical reviews indicating noticeable areas for improvement ({neg_pct}% negative across {total} review{'s' if total != 1 else ''})."
    else:
        return f"Balanced feedback across {total} review{'s' if total != 1 else ''}."