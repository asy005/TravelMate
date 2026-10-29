def guess_coordinates(name: str):
    if not name:
        return None

    mapping = {
        "mussoorie": (30.4598, 78.0664),
        "ooty": (11.4102, 76.6950),
        "darjeeling": (27.0360, 88.2627),
        "manali": (32.2396, 77.1887),
        "shimla": (31.1048, 77.1734),
        "coorg": (12.3375, 75.8069),
        "wayanad": (11.6854, 76.1320),
        "leh": (34.1526, 77.5771),
        "rishikesh": (30.0869, 78.2676),
        "nainital": (29.3803, 79.4636),
        "srinagar": (34.0837, 74.7973),
        "gangtok": (27.3389, 88.6065),

        "new delhi": (28.6139, 77.2090),
        "delhi": (28.6139, 77.2090),
        "jaipur": (26.9124, 75.7873),
                "taj mahal": (27.1751, 78.0421),
        "eiffel tower": (48.8584, 2.2945),
        "burj khalifa": (25.1972, 55.2744),
        "statue of liberty": (40.6892, -74.0445),
        "mount fuji": (35.3606, 138.7274),
        "golden gate bridge": (37.8199, -122.4783),
        "colosseum": (41.8902, 12.4922),
        "pyramids of giza": (29.9792, 31.1342),
        "sydney opera house": (-33.8568, 151.2153),
        "hampi": (15.3350, 76.4600),
        "jodhpur": (26.2389, 73.0243),
        "spiti valley": (32.2461, 78.0349),
        "spiti": (32.2461, 78.0349),
        "munnar": (10.0889, 77.0595),
        "jim corbett": (29.5300, 78.7747),
        "lakshadweep": (10.5667, 72.6417),
        "agra": (27.1767, 78.0081),
        "mumbai": (19.0760, 72.8777),
        "bangalore": (12.9716, 77.5946),
        "bengaluru": (12.9716, 77.5946),
        "chennai": (13.0827, 80.2707),
        "hyderabad": (17.3850, 78.4867),
        "kolkata": (22.5726, 88.3639),
        "kochi": (9.9312, 76.2673),
        "cochin": (9.9312, 76.2673),
        "goa": (15.2993, 74.1240),
        "kerala": (10.8505, 76.2711),
        "pondicherry": (11.9416, 79.8083),
        "puducherry": (11.9416, 79.8083),
        "varanasi": (25.3176, 82.9739),
        "rann of kutch": (23.7337, 69.8597),
        "vadodara": (22.3072, 73.1812),
        "india": (20.5937, 78.9629),

        "hiroshima": (34.3853, 132.4553),
        "tokyo": (35.6895, 139.6917),
        "kyoto": (35.0116, 135.7681),
        "japan": (35.6762, 139.6503),
        "paris": (48.8566, 2.3522),
        "france": (46.2276, 2.2137),
        "dubai": (25.2769, 55.2962),
        "uae": (23.4241, 53.8478),
        "berlin": (52.5200, 13.4050),
        "germany": (52.5200, 13.4050),
        "bali": (-8.3405, 115.0920),
        "maldives": (3.2028, 73.2207),
    }

    name_low = name.strip().lower()

    for key in sorted(mapping, key=len, reverse=True):
        if name_low == key or key in name_low:
            return mapping[key]

    return None

def get_nearby_attractions(lat: float, lon: float, max_results: int = 6):
    import os
    import requests
    from dotenv import load_dotenv

    load_dotenv()

    if lat is None or lon is None:
        return []

    api_key = os.getenv("OPENTRIPMAP_API_KEY", "").strip()

    fallback_places = {
        "mussoorie": {
            "coords": (30.4598, 78.0664),
            "places": [
                "Gun Hill",
                "Mall Road",
                "Company Garden",
                "Camel's Back Road",
            ],
        },
        "ooty": {
            "coords": (11.4102, 76.6950),
            "places": [
                "Government Botanical Garden",
                "Ooty Lake",
                "Doddabetta Peak",
                "Nilgiri Mountain Railway",
            ],
        },
        "darjeeling": {
            "coords": (27.0360, 88.2627),
            "places": [
                "Batasia Loop",
                "Darjeeling Himalayan Railway",
                "Padmaja Naidu Himalayan Zoological Park",
                "Tiger Hill",
            ],
        },
        "goa": {
            "coords": (15.2993, 74.1240),
            "places": [
                "Basilica of Bom Jesus",
                "Fort Aguada",
                "Old Goa",
                "Miramar Beach",
            ],
        },
        "kerala": {
            "coords": (10.8505, 76.2711),
            "places": [
                "Alleppey Backwaters",
                "Fort Kochi",
                "Munnar Tea Gardens",
                "Periyar Wildlife Sanctuary",
            ],
        },
        "shimla": {
            "coords": (31.1048, 77.1734),
            "places": [
                "The Ridge",
                "Mall Road",
                "Jakhoo Temple",
                "Kufri",
            ],
        },
        "manali": {
            "coords": (32.2396, 77.1887),
            "places": [
                "Hadimba Devi Temple",
                "Old Manali",
                "Solang Valley",
                "Vashisht Hot Springs",
            ],
        },
        "rishikesh": {
            "coords": (30.0869, 78.2676),
            "places": [
                "Lakshman Jhula area",
                "Ram Jhula",
                "Triveni Ghat",
                "Neer Garh Waterfall",
            ],
        },
        "coorg": {
            "coords": (12.3375, 75.8069),
            "places": [
                "Abbey Falls",
                "Raja's Seat",
                "Dubare Elephant Camp",
                "Madikeri Fort",
            ],
        },
        "pondicherry": {
            "coords": (11.9416, 79.8083),
            "places": [
                "Promenade Beach",
                "French Quarter",
                "Sri Aurobindo Ashram",
                "Paradise Beach",
            ],
        },
        "bangalore": {
            "coords": (12.9716, 77.5946),
            "places": [
                "Lalbagh Botanical Garden",
                "Cubbon Park",
                "Bangalore Palace",
                "Bannerghatta Biological Park",
                "Vidhana Soudha",
                "Tipu Sultan's Summer Palace",
            ],
        },
        "bengaluru": {
            "coords": (12.9716, 77.5946),
            "places": [
                "Lalbagh Botanical Garden",
                "Cubbon Park",
                "Bangalore Palace",
                "Bannerghatta Biological Park",
                "Vidhana Soudha",
                "Tipu Sultan's Summer Palace",
            ],
        },
        "delhi": {
            "coords": (28.6139, 77.2090),
            "places": [
                "Qutub Minar",
                "Humayun's Tomb",
                "Red Fort",
                "India Gate",
                "Lotus Temple",
            ],
        },
        "new delhi": {
            "coords": (28.6139, 77.2090),
            "places": [
                "Qutub Minar",
                "Humayun's Tomb",
                "Red Fort",
                "India Gate",
                "Lotus Temple",
            ],
        },
        "mumbai": {
            "coords": (19.0760, 72.8777),
            "places": [
                "Gateway of India",
                "Marine Drive",
                "Elephanta Caves",
                "Chhatrapati Shivaji Terminus",
            ],
        },
        "jaipur": {
            "coords": (26.9124, 75.7873),
            "places": [
                "Amber Palace",
                "Hawa Mahal",
                "City Palace",
                "Jantar Mantar",
                "Nahargarh Fort",
            ],
        },
    }

    def curated_fallback():
        for destination, info in fallback_places.items():
            ref_lat, ref_lon = info["coords"]
            if abs(lat - ref_lat) <= 0.25 and abs(lon - ref_lon) <= 0.25:
                return [
                    {
                        "name": place,
                        "distance_m": None,
                        "source": "curated",
                    }
                    for place in info["places"][:max_results]
                ]
        return []

    if api_key:
        url = "https://api.opentripmap.com/0.1/en/places/radius"
        params = {
            "radius": 5000,
            "lon": lon,
            "lat": lat,
            "kinds": "interesting_places",
            "format": "json",
            "apikey": api_key,
            "limit": max_results,
        }

        try:
            response = requests.get(url, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    live_places = [
                        {
                            "name": place.get("name"),
                            "distance_m": place.get("dist"),
                            "source": "opentripmap",
                        }
                        for place in data
                        if place.get("name")
                    ]
                    if live_places:
                        return live_places[:max_results]
                else:
                    print("[Attractions] Unexpected API response format.")
            elif response.status_code == 401:
                print(
                    "[Attractions] OpenTripMap API returned HTTP 401 Unauthorized "
                    "(invalid or unauthenticated OPENTRIPMAP_API_KEY). Using curated destination fallback."
                )
            else:
                print(
                    f"[Attractions] HTTP {response.status_code}; "
                    "trying curated fallback."
                )

        except (requests.exceptions.RequestException, ValueError) as exc:
            print(f"[Attractions] API request failed: {exc}")

    return curated_fallback()
