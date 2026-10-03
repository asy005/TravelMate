# app/services/geo_utils.py
import math
from typing import Tuple

def haversine_km(a: Tuple[float,float], b: Tuple[float,float]):
    # returns kilometers distance between a and b
    lat1, lon1 = a
    lat2, lon2 = b
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2*math.atan2(math.sqrt(x), math.sqrt(1-x))
    return R * c
