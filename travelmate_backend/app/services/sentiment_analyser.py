# app/services/sentiment_analyser.py
"""
Lightweight lexicon-based sentiment analyser for review text.

Design goals
------------
* Zero extra runtime dependencies -- uses only the Python standard library.
* Explainable: scoring rules are readable and testable.
* Safe on empty/None input: always returns a SentimentResult.
* Deterministic: same text always produces the same result.

Algorithm
---------
1. Tokenise text into lowercase words (strip punctuation).
2. Score each token against a curated positive/negative word set.
3. Apply a simple negation window (up to 3 tokens before a scored word flip
   its valence).
4. Normalise the raw sum to [-1, +1] using a soft clamp.
5. Map to a label:
     compound >= +0.05  -> 'positive'
     compound <= -0.05  -> 'negative'
     otherwise          -> 'neutral'
   (thresholds match the VADER convention for comparability.)

Accuracy note
-------------
This is a rule-based approximation suitable for travel review text.  It has
not been evaluated on a labelled benchmark; treat outputs as indicative, not
ground-truth.  For high-stakes decisions, replace with a transformer model.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Lexicon -- curated for travel / hospitality domain
# ---------------------------------------------------------------------------

_POSITIVE_WORDS: frozenset[str] = frozenset({
    # generic positive
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
    # generic negative
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

# Thresholds (VADER-compatible)
_POSITIVE_THRESHOLD = 0.05
_NEGATIVE_THRESHOLD = -0.05
_NEGATION_WINDOW = 3   # look-back distance for negation detection


@dataclass(frozen=True)
class SentimentResult:
    """Immutable result of sentiment analysis."""
    label: str          # 'positive' | 'neutral' | 'negative'
    score: float        # compound score in [-1.0, +1.0]
    token_count: int    # number of recognised sentiment tokens


def _tokenise(text: str) -> list[str]:
    """Lowercase, strip accents, split on non-alphabetic characters."""
    # Normalise unicode to strip accents
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()
    # Split on whitespace and punctuation
    return re.findall(r"[a-z']+", text)


def _soft_clamp(raw: float, token_count: int) -> float:
    """Normalise raw score to [-1, +1] using token count as denominator.

    We divide by token_count (which counts raw tokens before intensifier
    multiplication) to normalise, then clamp to [-1, +1].
    """
    if token_count == 0:
        return 0.0
    normalised = raw / max(token_count, 1)
    # Hard clamp to [-1, +1]
    return max(-1.0, min(1.0, normalised))


def analyse(text: Optional[str]) -> SentimentResult:
    """
    Analyse *text* and return a :class:`SentimentResult`.

    Parameters
    ----------
    text:
        The review body.  ``None``, empty string, or whitespace-only text
        returns a neutral result with score 0.0 and token_count 0.

    Returns
    -------
    SentimentResult
        Always returns a valid result; never raises.
    """
    if not text or not text.strip():
        return SentimentResult(label="neutral", score=0.0, token_count=0)

    tokens = _tokenise(text)
    raw_score = 0.0
    scored_token_count = 0
    negated_window = 0     # count-down until negation expires
    intensify = 1.0        # multiplier applied to next scored token

    for i, token in enumerate(tokens):
        # Decay negation window
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

        # Reset intensifier after it's been consumed (or after any non-ignore token)
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
    """
    Rating-only fallback used when review_text is empty.
    rating >= 4.0 -> positive, >= 3.0 -> neutral, < 3.0 -> negative.
    score is normalised linearly to [-1, +1] and clamped.
    """
    # Map [1,5] -> [-1,+1]: (rating - 3) / 2, then clamp
    score = round(max(-1.0, min(1.0, (rating - 3.0) / 2.0)), 4)
    if rating >= 4.0:
        label = "positive"
    elif rating >= 3.0:
        label = "neutral"
    else:
        label = "negative"
    return SentimentResult(label=label, score=score, token_count=0)


def classify_review(text: Optional[str], rating: Optional[float] = None) -> SentimentResult:
    """
    Main entry point.  Analyses *text*; falls back to rating-based
    classification if text is blank.

    Parameters
    ----------
    text:
        Review body (may be None or empty).
    rating:
        Numeric star rating (1–5); used as fallback only.
    """
    result = analyse(text)
    if result.token_count == 0 and rating is not None:
        return classify_by_rating(rating)
    return result
