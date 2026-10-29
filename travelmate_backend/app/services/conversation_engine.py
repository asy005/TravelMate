import json
import re
from typing import Dict, Any, List, Tuple, Optional
from app.services.llm_gateway import chat_completion, LLMGatewayError

ALL_SLOTS = [
    "origin",
    "destination",
    "budget",
    "travelers",
    "start_date",
    "duration_days",
    "travel_style",
    "interests",
    "transport_pref",
    "food_pref",
    "accommodation_pref",
    "weather_pref",
    "accessibility",
    "additional_notes",
]

REQUIRED_SLOTS = [
    "budget",
    "duration_days",
    "travelers",
    "travel_style",
]

EMPTY_SLOTS: Dict[str, Any] = {
    slot: None for slot in ALL_SLOTS
}

WORD_NUMBERS: Dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "twenty-one": 21, "twenty-two": 22, "twenty-three": 23, "twenty-four": 24, "twenty-five": 25,
    "twenty-six": 26, "twenty-seven": 27, "twenty-eight": 28, "twenty-nine": 29, "thirty": 30,
}

def _parse_number_word_or_digit(val: str) -> Optional[int]:
    if not val:
        return None
    val = val.strip().lower()
    if val.isdigit():
        return int(val)
    return WORD_NUMBERS.get(val)

def merge_slots(
    old_slots: Dict[str, Any],
    new_slots: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(EMPTY_SLOTS)
    merged.update(old_slots or {})

    for key in ALL_SLOTS:
        value = (new_slots or {}).get(key)
        if value not in (None, "", [], {}):
            merged[key] = value

    for key, value in (new_slots or {}).items():
        if value not in (None, "", [], {}):
            merged[key] = value

    for num_key in ("duration_days", "travelers"):
        if isinstance(merged.get(num_key), str) and merged[num_key].strip().isdigit():
            merged[num_key] = int(merged[num_key].strip())

    return merged

def missing_required_slots(
    slots: Dict[str, Any],
) -> List[str]:
    return [
        slot for slot in REQUIRED_SLOTS
        if slots.get(slot) is None
        or slots.get(slot) == ""
        or slots.get(slot) == []
    ]

def is_ready_for_plan(slots: Dict[str, Any]) -> bool:
    return not missing_required_slots(slots)

def extract_explicit_slots(message: str) -> Dict[str, Any]:
    text = message.lower()
    extracted: Dict[str, Any] = {}

    origin_match = re.search(
        r"\bfrom\s+([a-z][a-z .'-]*?)(?=\s+(?:to|for|with|on|and|by|budget|during)\b|[,;.!?]|$)",
        text,
        re.IGNORECASE,
    )
    if origin_match:
        origin = origin_match.group(1).strip(" .,'-\t")
        if origin:
            extracted["origin"] = origin.title()

    dest_match = re.search(
        r"\b(?:plan\s+(?:my|a)\s+trip\s+to|trip\s+to|travel\s+to|visit(?:ing)?|going\s+to|head\s+to|explore|choose|select)\s+([a-z][a-z .'-]*?)(?=\s+(?:from|for|with|on|and|by|budget|during|in)\b|[,;.!?]|$)",
        text,
        re.IGNORECASE,
    )
    if dest_match:
        dest_val = dest_match.group(1).strip(" .,'-\t")
        if dest_val and dest_val.lower() not in ("a", "the", "my", "some", "somewhere", "anywhere"):
            extracted["destination"] = dest_val.title()

    # ── 1. Budget extraction (tolerant of approximations, k suffix, currency) ──
    budget_qualifiers = r"(?:approximately|approx\.?|around|about|under|below|up\s+to|within|nearly|roughly|max(?:imum)?|close\s+to|near|budget(?:\s+(?:is|of))?)"
    currency = r"(?:₹\s*|rs\.?\s*|inr\s*)"
    amount_pattern = r"(\d[\d,]*(?:\.\d+)?\s*k?)"

    budget_match = re.search(
        rf"\b{budget_qualifiers}\s*(?:is|of|:)?\s*{currency}?{amount_pattern}",
        text,
        re.IGNORECASE,
    )
    if not budget_match:
        budget_match = re.search(rf"{currency}{amount_pattern}", text, re.IGNORECASE)
    if not budget_match:
        budget_match = re.search(rf"\b{amount_pattern}\s*(?:rupees|inr|budget)\b", text, re.IGNORECASE)
    if not budget_match:
        budget_match = re.search(r"^\s*(?:around|about|approx(?:imately)?|under)?\s*(\d[\d,]*(?:\.\d+)?k)\s*$", text, re.IGNORECASE)
    if not budget_match:
        # Standalone clean 4-6 digit budget: e.g. "15000", "25000"
        budget_match = re.search(r"^\s*(\d{4,6})\s*$", text)

    if budget_match:
        raw_budget = budget_match.group(1).lower().replace(",", "").replace(" ", "")
        if raw_budget.endswith("k"):
            try:
                raw_budget = str(int(float(raw_budget[:-1]) * 1000))
            except ValueError:
                pass
        extracted["budget"] = raw_budget
    else:
        # Qualitative budget keywords
        if re.search(r"\b(?:luxury|expensive|high[- ]end|lavish)\b", text):
            extracted["budget"] = "luxury"
        elif re.search(r"\b(?:low[- ]?budget|cheap|economical|pocket[- ]?friendly|tight\s+budget)\b", text):
            extracted["budget"] = "low"
        elif re.search(r"\b(?:moderate|medium|mid[- ]?range|reasonable)\b", text):
            extracted["budget"] = "medium"

    # ── 2. Duration extraction (tolerant of word numbers, colloquial phrases) ──
    if re.search(r"\b(?:a\s+)?long\s+weekend\b", text):
        extracted["duration_days"] = 3
    elif re.search(r"\b(?:a\s+)?weekend\b", text):
        extracted["duration_days"] = 2
    elif re.search(r"\b(?:a\s+|one\s+)week\b", text):
        extracted["duration_days"] = 7
    elif re.search(r"\btwo\s+weeks\b", text):
        extracted["duration_days"] = 14
    elif re.search(r"\b(?:a\s+)?couple\s+of\s+days\b", text):
        extracted["duration_days"] = 2
    elif re.search(r"\b(?:a\s+)?few\s+days\b", text):
        extracted["duration_days"] = 3
    else:
        num_word_pat = r"(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty|twenty-five|thirty)"
        dur_match = re.search(
            rf"\b(?:about|around|approx(?:imately)?|for)?\s*{num_word_pat}\s*[- ]?(?:days?|nights?)\b",
            text,
            re.IGNORECASE,
        )
        if dur_match:
            parsed_dur = _parse_number_word_or_digit(dur_match.group(1))
            if parsed_dur and 1 <= parsed_dur <= 60:
                extracted["duration_days"] = parsed_dur
        else:
            range_match = re.search(r"\b(\d{1,2})\s*(?:to|-)\s*(\d{1,2})\s*(?:days?|nights?)\b", text)
            if range_match:
                extracted["duration_days"] = int(range_match.group(2))

    # ── 3. Travellers extraction (tolerant of solo, spoken numbers, groups) ──
    solo_match = re.search(
        r"\b(?:just\s+me|only\s+me|alone|solo|myself|by\s+myself|single\s+travel(?:l)?er|single\s+person|one\s+person|1\s+person|for\s+1\b|for\s+one\b)\b",
        text,
        re.IGNORECASE,
    )
    if solo_match:
        extracted["travelers"] = 1
    elif re.search(
        r"\b(?:two\s+people|2\s+people|two\s+persons|2\s+persons|two\s+travel(?:l)?ers|2\s+travel(?:l)?ers|couple|for\s+2\b|for\s+two\b|with\s+my\s+(?:partner|wife|husband|spouse|friend|girlfriend|boyfriend)|me\s+and\s+my\s+(?:partner|wife|husband|spouse|friend|girlfriend|boyfriend))\b",
        text,
        re.IGNORECASE,
    ):
        extracted["travelers"] = 2
    else:
        # Check "X of us": e.g. "four of us", "4 of us", "two of us"
        of_us_match = re.search(
            r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+of\s+us\b",
            text,
            re.IGNORECASE,
        )
        if of_us_match:
            parsed_count = _parse_number_word_or_digit(of_us_match.group(1))
            if parsed_count:
                extracted["travelers"] = parsed_count
        else:
            travelers_match = re.search(
                r"\b(?:for\s+)?(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:people|persons|travelers|travellers|adults|members|pax|guests)\b",
                text,
                re.IGNORECASE,
            )
            if travelers_match:
                parsed_t = _parse_number_word_or_digit(travelers_match.group(1))
                if parsed_t:
                    extracted["travelers"] = parsed_t
            else:
                fam_m = re.search(
                    r"\bfamily\s+of\s+(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\b",
                    text,
                    re.IGNORECASE,
                )
                if fam_m:
                    parsed_fam = _parse_number_word_or_digit(fam_m.group(1))
                    if parsed_fam:
                        extracted["travelers"] = parsed_fam

    style_patterns = [
        (
            "relaxing",
            r"\brelax(?:ing|ed)?\b|\bleisure\b|\bchill(?:ing)?\b|\bunwind(?:ing)?\b",
        ),
        (
            "adventurous",
            r"\badventur(?:e|ous|ously)\b|\bthrill[- ]seeking\b|\baction[- ]packed\b",
        ),
        (
            "cultural",
            r"\bcultural\b|\bheritage\b|\bhistorical tour\b|\bexplor(?:e|ing|ation)\b",
        ),
        (
            "romantic",
            r"\bromantic\b|\bcouple getaway\b|\bhoneymoon\b",
        ),
        (
            "nature",
            r"\bnature[- ]?focused\b|\bnature trip\b",
        ),
        (
            "spiritual",
            r"\bspiritual\b|\bpilgrimage\b",
        ),
        (
            "family",
            r"\bfamily[- ]friendly\b|\bfamily vacation\b",
        ),
    ]

    for style, pattern in style_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            extracted["travel_style"] = style
            break

    if re.search(r"\bby car\b|\bdrive\b|\bdriving\b", text):
        extracted["transport_pref"] = "car"

    elif re.search(r"\bby train\b|\btrain travel\b", text):
        extracted["transport_pref"] = "train"

    elif re.search(r"\bby bus\b|\bbus travel\b", text):
        extracted["transport_pref"] = "bus"

    elif re.search(r"\bby flight\b|\bflying\b", text):
        extracted["transport_pref"] = "flight"

    if re.search(r"\bvegan\b", text):
        extracted["food_pref"] = "vegan"

    elif re.search(r"\bvegetarian\b", text):
        extracted["food_pref"] = "vegetarian"

    interest_patterns = [
        (
            r"\bhill stations?\b|\bhills?\b|\bmountains?\b|"
            r"\bmountainous\b|\bcool climate\b",
            "hill station",
        ),
        (r"\bbeach(?:es)?\b|\bcoastal\b|\bseaside\b", "beaches"),
        (r"\bheritage\b|\bhistorical places?\b|\bhistory\b", "heritage"),
        (r"\bforests?\b|\bwildlife\b|\bjungles?\b", "forest"),
        (r"\bdeserts?\b", "desert"),
        (r"\badventure\b|\badventurous activities\b", "adventure"),
        (r"\bcities\b|\bcity sightseeing\b|\burban\b", "urban"),
        (r"\bnature\b|\bwaterfalls?\b", "nature"),
    ]

    for pattern, interest in interest_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            extracted["interests"] = interest
            break

    return extracted

def extract_contextual_slot(last_assistant_msg: str, user_message: str) -> Dict[str, Any]:
    """
    Extracts the slot specifically asked for by the assistant when the user
    provides a concise response.
    """
    text = user_message.lower().strip()
    last_q = (last_assistant_msg or "").lower()
    res: Dict[str, Any] = {}

    if any(k in last_q for k in ("budget", "how much", "cost", "spending")):
        m = re.search(r"^(?:around|about|approx(?:imately)?|under|up to)?\s*(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d+)?k?)\s*(?:rupees|inr)?$", text)
        if m:
            raw = m.group(1).replace(",", "")
            if raw.endswith("k"):
                raw = str(int(float(raw[:-1]) * 1000))
            if raw.isdigit() and int(raw) >= 500:
                res["budget"] = raw
        elif text in ("low", "medium", "moderate", "luxury", "high"):
            res["budget"] = text

    elif any(k in last_q for k in ("days", "duration", "how long")):
        m = re.search(r"^(?:about|around|approx(?:imately)?|for)?\s*(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|a weekend|a long weekend|a week)\s*(?:days?|nights?)?$", text)
        if m:
            val = m.group(1)
            if val == "a long weekend":
                res["duration_days"] = 3
            elif val == "a weekend":
                res["duration_days"] = 2
            elif val == "a week":
                res["duration_days"] = 7
            elif val.isdigit():
                res["duration_days"] = int(val)
            elif val in WORD_NUMBERS:
                res["duration_days"] = WORD_NUMBERS[val]

    elif any(k in last_q for k in ("how many people", "how many travelers", "who is coming", "who's traveling", "travelers")):
        m = re.search(r"^(?:for\s+)?(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|just me|alone|solo|couple)\s*(?:people|persons|travelers|travellers|of us)?$", text)
        if m:
            val = m.group(1)
            if val in ("just me", "alone", "solo", "one", "1"):
                res["travelers"] = 1
            elif val in ("couple", "two", "2"):
                res["travelers"] = 2
            elif val.isdigit():
                res["travelers"] = int(val)
            elif val in WORD_NUMBERS:
                res["travelers"] = WORD_NUMBERS[val]

    return res

def _system_prompt(prior_slots: Dict[str, Any]) -> str:
    known = {
        key: value
        for key, value in prior_slots.items()
        if value not in (None, "", [], {})
    }

    schema = {
        "slots": {key: None for key in ALL_SLOTS},
        "reply": "Short, natural reply",
        "ready_for_plan": False,
    }

    return (
        "You are TravelMate's friendly AI travel consultant. "
        "Talk naturally, like a helpful human travel agent, never like a robotic form or questionnaire.\n\n"
        "Previously collected preferences:\n"
        f"{json.dumps(known, ensure_ascii=False)}\n\n"
        "Extract preferences explicitly stated in the latest user message. "
        "One message may contain several preferences. Never ask for a "
        "preference that is already known. Use null for unchanged or "
        "unstated slots. Do not invent values. Never dump multiple questions or use a numbered list. Ask at most one friendly follow-up question "
        "for a missing required preference.\n\n"
        "Required preferences: budget, duration_days, travelers, "
        "travel_style.\n\n"
        "Return only a valid JSON object with this structure:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )

def _fallback_next_question(slots: Dict[str, Any]) -> str:
    prompts = {
        "budget": "What's your approximate budget for this trip?",
        "duration_days": "How many days are you planning to travel?",
        "travelers": "How many people will be traveling?",
        "travel_style": (
            "What kind of trip would you prefer: relaxing, "
            "adventurous, cultural, or something else?"
        ),
    }

    missing = missing_required_slots(slots)

    if missing:
        return prompts[missing[0]]

    return (
        "Great! I have the essential details. "
        "Let's put together your travel plan."
    )

def _asks_for_known_slot(
    reply: str,
    slots: Dict[str, Any],
) -> bool:
    text = reply.lower()

    question_patterns = {
        "budget": r"\bbudget\b|\bhow much\b",
        "duration_days": r"\bhow many days\b|\btrip duration\b",
        "travelers": r"\bhow many people\b|\bhow many travelers\b",
        "travel_style": r"\btravel style\b|\bkind of trip\b",
    }

    for slot, pattern in question_patterns.items():
        if slots.get(slot) and re.search(pattern, text):
            return True

    return False

def process_message(
    prior_slots: Dict[str, Any],
    conversation_history: List[Dict[str, str]],
    user_message: str,
) -> Tuple[str, Dict[str, Any], bool]:

    prior = merge_slots(EMPTY_SLOTS, prior_slots or {})
    explicit_slots = extract_explicit_slots(user_message)

    # Check if the assistant recently asked a question to contextualize concise answers
    last_asst_msg = ""
    for msg in reversed(conversation_history or []):
        if msg.get("role") == "assistant":
            last_asst_msg = msg.get("content", "")
            break

    if last_asst_msg:
        contextual = extract_contextual_slot(last_asst_msg, user_message)
        explicit_slots = merge_slots(explicit_slots, contextual)

    known_slots = merge_slots(prior, explicit_slots)

    messages = [
        {
            "role": "system",
            "content": _system_prompt(known_slots),
        }
    ]

    messages.extend((conversation_history or [])[-12:])
    messages.append({
        "role": "user",
        "content": user_message,
    })

    try:
        raw = chat_completion(
            messages,
            json_mode=True,
            temperature=0.2,
        )

        parsed = json.loads(raw)

        if not isinstance(parsed, dict):
            raise ValueError("LLM response must be a JSON object")

        llm_slots = parsed.get("slots", {}) or {}

        updated_slots = merge_slots(known_slots, llm_slots)
        updated_slots = merge_slots(updated_slots, explicit_slots)

        ready = is_ready_for_plan(updated_slots)

        reply = str(parsed.get("reply") or "").strip()

        if ready:
            if not reply or _asks_for_known_slot(reply, updated_slots):
                reply = (
                    "I've found 3 top destination recommendations tailored to your style and preferences! "
                    "Choose your preferred destination below to view the itinerary and trip plan, or ask for alternatives to adjust."
                )
        else:
            has_numbered_list = bool(
                re.search(r"(?:^|\n)\s*[1-9][\.\)]\s+", reply)
                or re.search(r"\b1[\.\)]\s+.*\b2[\.\)]\s+", reply, re.DOTALL)
            )
            if (
                not reply
                or has_numbered_list
                or _asks_for_known_slot(reply, updated_slots)
            ):
                reply = _fallback_next_question(updated_slots)

        return reply, updated_slots, ready

    except (
        LLMGatewayError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ):
        updated_slots = known_slots
        ready = is_ready_for_plan(updated_slots)

        return (
            _fallback_next_question(updated_slots),
            updated_slots,
            ready,
        )
