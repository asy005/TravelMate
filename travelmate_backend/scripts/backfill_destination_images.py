"""
backfill_destination_images.py
--------------------------------
Backfills the thumbnail_url field on Destination rows whose images exist
in the dataset images directory.

Usage:
    python scripts/backfill_destination_images.py [--dry-run]

Options:
    --dry-run   Print what would be updated without writing to the DB.

Must be run from the travelmate_backend directory (or set PYTHONPATH accordingly).
"""

import sys
import os
import argparse
from pathlib import Path

# ── Ensure the backend is importable ────────────────────────────────────────
_BACKEND_DIR = Path(__file__).resolve().parents[1]  # travelmate_backend/
sys.path.insert(0, str(_BACKEND_DIR))

from app.database import SessionLocal
from app.models.destination import Destination
from app.utils.image_resolver import resolve_destination_image


def main():
    parser = argparse.ArgumentParser(description="Backfill destination thumbnail_url from dataset images")
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing to DB")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        destinations = db.query(Destination).all()
        total = len(destinations)
        already_set = 0
        will_update = 0
        no_image = 0

        for d in destinations:
            if d.thumbnail_url:
                already_set += 1
                continue

            url = resolve_destination_image(d.id, getattr(d, "csv_destination_id", None))
            if url:
                will_update += 1
                if not args.dry_run:
                    d.thumbnail_url = url
            else:
                no_image += 1

        if not args.dry_run:
            db.commit()
            print(f"[backfill] Committed {will_update} thumbnail_url updates.")
        else:
            print(f"[backfill --dry-run] Would update {will_update} rows.")

        print(f"  Total destinations : {total}")
        print(f"  Already had URL    : {already_set}")
        print(f"  Image found        : {will_update}")
        print(f"  No image found     : {no_image}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
