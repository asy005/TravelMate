from app.database import SessionLocal
from app.models.destination import Destination

DESTINATION_DETAILS = {
    "mussoorie": {
        "description": (
            "A scenic Himalayan hill station in Uttarakhand, known for "
            "Mall Road, Gun Hill viewpoints, Company Garden, and mountain walks."
        ),
        "lat": 30.4598,
        "lon": 78.0664,
    },
    "ooty": {
        "description": (
            "A popular hill station in the Nilgiri Hills of Tamil Nadu, "
            "known for botanical gardens, tea estates, Ooty Lake, and "
            "the historic Nilgiri Mountain Railway."
        ),
        "lat": 11.4102,
        "lon": 76.6950,
    },
    "darjeeling": {
        "description": (
            "A Himalayan hill town in West Bengal, famous for tea gardens, "
            "views of the Kanchenjunga range, and the Darjeeling Himalayan Railway."
        ),
        "lat": 27.0360,
        "lon": 88.2627,
    },
    "goa": {
        "description": (
            "A coastal destination in western India known for sandy beaches, "
            "Portuguese-era heritage in Old Goa, local seafood, and sunset views."
        ),
        "lat": 15.2993,
        "lon": 74.1240,
    },
    "kerala": {
        "description": (
            "A southern Indian state known for tranquil backwaters, houseboat "
            "cruises, tea-covered hills, wildlife, and tropical landscapes."
        ),
        "lat": 10.8505,
        "lon": 76.2711,
    },
    "shimla": {
        "description": (
            "The capital of Himachal Pradesh, known for colonial-era buildings, "
            "The Ridge, Mall Road, and scenic Himalayan surroundings."
        ),
        "lat": 31.1048,
        "lon": 77.1734,
    },
    "manali": {
        "description": (
            "A mountain destination in Himachal Pradesh known for alpine "
            "scenery, the Beas River, nearby villages, and outdoor adventures."
        ),
        "lat": 32.2396,
        "lon": 77.1887,
    },
    "rishikesh": {
        "description": (
            "A riverside destination in Uttarakhand known for the Ganges, "
            "suspension bridges, yoga retreats, and outdoor adventure activities."
        ),
        "lat": 30.0869,
        "lon": 78.2676,
    },
    "coorg": {
        "description": (
            "A green hill region in Karnataka known for coffee plantations, "
            "waterfalls, forest scenery, and Kodava culture."
        ),
        "lat": 12.3375,
        "lon": 75.8069,
    },
    "pondicherry": {
        "description": (
            "A coastal town known for its French Quarter, colourful colonial "
            "architecture, seaside promenade, cafés, and nearby Auroville."
        ),
        "lat": 11.9416,
        "lon": 79.8083,
    },
}

GENERIC_DESCRIPTIONS = {
    "",
    "relaxing",
    "adventure",
    "romantic",
    "cultural",
    "nature",
    "historical",
    "beach",
    "hill station",
}

def main():
    db = SessionLocal()
    updated = 0
    not_found = []

    try:
        for name, details in DESTINATION_DETAILS.items():
            destination = (
                db.query(Destination)
                .filter(Destination.name.ilike(name))
                .first()
            )

            if destination is None:
                not_found.append(name)
                continue

            description = (destination.description or "").strip().lower()

            if description in GENERIC_DESCRIPTIONS:
                destination.description = details["description"]

            # Populate missing coordinates only; preserve existing coordinates.
            if destination.lat is None:
                destination.lat = details["lat"]

            if destination.lon is None:
                destination.lon = details["lon"]

            updated += 1
            print(
                f"Updated: {destination.name} | "
                f"Description: {destination.description} | "
                f"Coordinates: ({destination.lat}, {destination.lon})"
            )

        db.commit()

        print(f"\nCompleted. Records processed: {updated}")

        if not_found:
            print("Names not found in database:", ", ".join(not_found))

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()