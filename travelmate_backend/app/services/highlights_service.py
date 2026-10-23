from typing import List, Dict
import re

DESTINATION_ACTIVITIES = {
    "bangalore": [
        "Explore the lush botanical beauty of Lalbagh and the sprawling green expanse of Cubbon Park.",
        "Visit the magnificent Tudor-style Bangalore Palace and Tipu Sultan's Summer Palace.",
        "Experience the city's celebrated cafe culture, craft breweries, and tech hub energy in Indiranagar and Koramangala.",
        "Take a scenic day trip to Nandi Hills or explore the wildlife safari at Bannerghatta Biological Park.",
    ],
    "bengaluru": [
        "Explore the lush botanical beauty of Lalbagh and the sprawling green expanse of Cubbon Park.",
        "Visit the magnificent Tudor-style Bangalore Palace and Tipu Sultan's Summer Palace.",
        "Experience the city's celebrated cafe culture, craft breweries, and tech hub energy in Indiranagar and Koramangala.",
        "Take a scenic day trip to Nandi Hills or explore the wildlife safari at Bannerghatta Biological Park.",
    ],
    "kerala": [
        "Explore the backwaters and enjoy a peaceful boat ride.",
        "Visit a local tea garden or spice plantation.",
        "Discover Kerala's local cuisine and natural surroundings.",
    ],
    "goa": [
        "Relax on a beach and enjoy the coastal scenery.",
        "Explore Old Goa's historic churches and heritage sites.",
        "Enjoy a coastal sunset and sample local Goan cuisine.",
    ],
    "gokarna": [
        "Visit Mahabaleshwar Temple and explore Gokarna's tranquil coastal town lanes.",
        "Trek between the scenic shores of Om Beach, Kudle Beach, and Half Moon Beach.",
        "Enjoy peaceful sunsets over the Arabian Sea with fresh coastal delicacies.",
    ],
    "ganpatipule": [
        "Visit the sacred Shri Swayambhu Ganpati Temple right beside the clean shoreline.",
        "Explore the Prachin Konkan Museum to learn about traditional coastal life and heritage.",
        "Take a scenic coastal drive along the Aare-Ware sea road.",
    ],
    "pondicherry": [
        "Stroll along the historic French Quarter with its mustard-yellow colonial villas.",
        "Enjoy a peaceful evening walk along the Promenade Beach.",
        "Visit Sri Aurobindo Ashram and the experimental township of Auroville.",
    ],
    "puducherry": [
        "Stroll along the historic French Quarter with its mustard-yellow colonial villas.",
        "Enjoy a peaceful evening walk along the Promenade Beach.",
        "Visit Sri Aurobindo Ashram and the experimental township of Auroville.",
    ],
    "shimla": [
        "Walk along Mall Road and explore local shops and cafes.",
        "Visit the Ridge and enjoy views of the surrounding hills.",
        "Explore nearby nature trails and scenic viewpoints.",
        "Visit Jakhoo Temple on Jakhoo Hill for panoramic valley views.",
        "Take a scenic excursion to Kufri for alpine views and walking trails.",
    ],
    "manali": [
        "Explore Old Manali and enjoy views of the Beas River.",
        "Visit Hadimba Devi Temple and its surrounding cedar forest.",
        "Enjoy the mountain scenery and local cafes.",
    ],
    "solang valley": [
        "Experience thrilling adventure sports including paragliding, zorbing, and quad biking.",
        "Ride the Solang ropeway for breathtaking panoramic views of snow-capped peaks.",
        "Enjoy high-altitude alpine trails and winter snow activities.",
    ],
    "ooty": [
        "Visit Ooty Lake and enjoy the surrounding gardens.",
        "Explore the Government Botanical Garden.",
        "Take in the Nilgiri hills and explore local tea shops.",
    ],
    "coorg": [
        "Visit a coffee plantation and learn about local coffee growing.",
        "Explore Abbey Falls and enjoy the surrounding greenery.",
        "Enjoy Coorg's hill scenery and local Kodava cuisine.",
    ],
    "rishikesh": [
        "Walk along the Ganges and explore the riverfront ghats.",
        "Visit the area's well-known suspension bridges.",
        "Enjoy a peaceful riverside evening.",
    ],
    "darjeeling": [
        "Explore the tea gardens and enjoy views of the surrounding hills.",
        "Visit the Darjeeling Himalayan Railway area.",
        "Walk around local markets and sample Darjeeling tea.",
    ],
    "mussoorie": [
        "Explore Mall Road and browse local shops and cafes.",
        "Visit Gun Hill for views of the surrounding hills.",
        "Enjoy Company Garden or walk near Camel's Back Road.",
    ],
    "delhi": [
        "Visit UNESCO World Heritage sites including Qutub Minar, Humayun's Tomb, and Red Fort.",
        "Stroll through the historic lanes and spice markets of Old Delhi.",
        "Explore modern landmarks, museums, and vibrant dining districts across New Delhi.",
    ],
    "new delhi": [
        "Visit UNESCO World Heritage sites including Qutub Minar, Humayun's Tomb, and Red Fort.",
        "Stroll through the historic lanes and spice markets of Old Delhi.",
        "Explore modern landmarks, museums, and vibrant dining districts across New Delhi.",
    ],
    "mumbai": [
        "Visit the iconic Gateway of India and take a stroll along Marine Drive.",
        "Explore the historic heritage architecture of South Mumbai and Chhatrapati Shivaji Terminus.",
        "Sample renowned Mumbai street food and visit the Elephanta Caves.",
    ],
    "jaipur": [
        "Tour the majestic Amber Fort and enjoy panoramic views of the Aravalli hills.",
        "Admire the intricate facade of Hawa Mahal and the royal City Palace.",
        "Shop for handicrafts, textiles, and gemstones in the vibrant bazaars of the Pink City.",
    ],
}

NOISE_PATTERNS = [
    r"\bISBN\b",
    r"\bwww\.",
    r"\.com\b",
    r"\bunique destinations\b",
    r"\bpage\s+\d+\b",
    r"\bvol(?:ume)?\.?\s*\d+\b",
]

def _is_useful_sentence(sentence: str) -> bool:
    sentence = sentence.strip()

    if len(sentence) < 25 or len(sentence) > 240:
        return False

    if not re.search(r"[a-zA-Z]{3,}", sentence):
        return False

    if any(
        re.search(pattern, sentence, re.IGNORECASE)
        for pattern in NOISE_PATTERNS
    ):
        return False

    letters = sum(char.isalpha() for char in sentence)
    if letters / max(len(sentence), 1) < 0.55:
        return False

    return True

def extract_sentences(text: str, max_sentences: int = 3) -> List[str]:
    if not isinstance(text, str) or not text.strip():
        return []

    text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[.!?])\s+", text)

    results = []
    for sentence in sentences:
        sentence = sentence.strip()

        if _is_useful_sentence(sentence) and sentence not in results:
            results.append(sentence)

        if len(results) >= max_sentences:
            break

    return results

def top_highlights_from_rag(
    rag_result: Dict,
    max_items: int = 3,
    destination_name: str = "",
) -> List[str]:
    key = (destination_name or "").strip().lower()
    max_items = max(0, min(int(max_items), 10))

    if max_items == 0:
        return []

    # 1. Curated destination activities take priority for precision
    if key in DESTINATION_ACTIVITIES:
        return DESTINATION_ACTIVITIES[key][:max_items]

    rag_result = rag_result or {}
    snippets = rag_result.get("snippets") or []
    highlights = []

    foreign_places = [
        "gokarna", "ganpatipule", "pondicherry", "puducherry", "goa", "kerala",
        "kudle beach", "om beach", "miramar beach", "solang valley", "hadimba"
    ]
    should_filter_foreign = bool(key and key not in foreign_places)

    for snippet in snippets:
        if isinstance(snippet, dict):
            text = snippet.get("text", "")
        else:
            text = getattr(snippet, "page_content", "")

        for sentence in extract_sentences(text, max_sentences=2):
            if should_filter_foreign:
                sent_lower = sentence.lower()
                if any(fp in sent_lower for fp in foreign_places):
                    continue
                if key in ("bangalore", "bengaluru", "delhi", "new delhi", "jaipur", "shimla", "manali", "coorg"):
                    if any(w in sent_lower for w in ("beach", "coastal", "surf", "snorkeling", "scuba")):
                        continue

            if sentence not in highlights:
                highlights.append(sentence)

            if len(highlights) >= max_items:
                return highlights

    fallback = rag_result.get("fallback") or {}
    description = fallback.get("description", "")

    for sentence in extract_sentences(description, max_sentences=max_items):
        if sentence not in highlights:
            highlights.append(sentence)

        if len(highlights) >= max_items:
            return highlights

    context = rag_result.get("context", "")
    for sentence in extract_sentences(context, max_sentences=max_items):
        if should_filter_foreign:
            sent_lower = sentence.lower()
            if any(fp in sent_lower for fp in foreign_places):
                continue
            if key in ("bangalore", "bengaluru", "delhi", "new delhi", "jaipur", "shimla", "manali", "coorg"):
                if any(w in sent_lower for w in ("beach", "coastal", "surf", "snorkeling", "scuba")):
                    continue

        if sentence not in highlights:
            highlights.append(sentence)

        if len(highlights) >= max_items:
            break

    # If still empty and destination is known, provide safe destination-grounded highlights
    if not highlights and destination_name:
        highlights = [
            f"Explore verified cultural and heritage landmarks across {destination_name}.",
            f"Discover popular nature reserves, parks, and scenic viewpoints near {destination_name}.",
            f"Sample authentic regional specialties and visit local market quarters in {destination_name}."
        ]

    return highlights[:max_items]
