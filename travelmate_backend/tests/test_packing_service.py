from app.services.packing_service import generate_packing


def test_tropical_beach_trip_packing():
    items = generate_packing("tropical", 5, ["beach"])
    assert "sunscreen" in items
    assert "swimwear" in items
    assert "toiletries" in items
    assert "extra clothes" not in items  # only added for >7 day trips


def test_cold_trekking_trip_packing():
    items = generate_packing("cold", 10, ["trekking"])
    assert "warm jacket" in items
    assert "trekking shoes" in items
    assert "extra clothes" in items
    assert "medicine kit" in items


def test_no_duplicate_items():
    items = generate_packing("tropical", 3, ["beach", "beach"])
    assert len(items) == len(set(items))
