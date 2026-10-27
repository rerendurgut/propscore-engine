"""Configuration, bounding boxes, Geofabrik/Overpass/Overture mappings, and 9-category scoring weights."""

from dataclasses import dataclass
from typing import Dict, List, Tuple

# Metric CRS for Bursa / Western Turkey (UTM Zone 35N)
METRIC_CRS = "EPSG:32635"
WGS84_CRS = "EPSG:4326"

# Average pedestrian walking speed: 4.5 km/h = 75 meters / minute
WALKING_SPEED_M_PER_MIN = 75.0

# Predefined Pilot Regions in Bursa Nilüfer
REGIONS: Dict[str, Dict[str, object]] = {
    "nilufer_fsm": {
        "name": "Bursa / Nilüfer (Özlüce • 23 Nisan • Ataevler • FSM • İhsaniye • Beşevler • Konak)",
        "bbox": (28.895, 40.198, 29.006, 40.245),
        "center": (40.2195, 28.9620),
        "zoom": 14.0,
    },
    "nilufer_ozluce": {
        "name": "Bursa / Nilüfer (Özlüce • 29 Ekim • Yüzüncüyıl • 23 Nisan • Altınşehir)",
        "bbox": (28.885, 40.210, 28.952, 40.244),
        "center": (40.2260, 28.9180),
        "zoom": 14.5,
    },
    "nilufer_gorukle": {
        "name": "Bursa / Nilüfer (Görükle • Dumlupınar • Üniversite)",
        "bbox": (28.810, 40.210, 28.865, 40.242),
        "center": (40.2260, 28.8380),
        "zoom": 14.5,
    },
    "nilufer_full": {
        "name": "Bursa / Nilüfer (Tüm İlçe Geneli)",
        "bbox": (28.815, 40.190, 29.012, 40.255),
        "center": (40.2200, 28.9450),
        "zoom": 13.0,
    },
}

EXCLUDED_ROAD_FCLASSES = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "bridleway",
    "bus_guideway",
    "raceway",
}


@dataclass
class CategoryConfig:
    key: str
    label_tr: str
    weight: float
    fclasses: List[str]
    ideal_walk_mins: float  # ~100 pts threshold (minutes)
    max_walk_mins: float    # low pts threshold (minutes)
    icon: str
    color: str


# 9 Distinct PropScore Categories
CATEGORIES: Dict[str, CategoryConfig] = {
    "metro": CategoryConfig(
        key="metro",
        label_tr="BursaRay Metro & Raylı Sistem",
        weight=0.16,
        fclasses=["railway_station", "railway_halt", "tram_stop", "subway_entrance", "station"],
        ideal_walk_mins=5.0,
        max_walk_mins=24.0,
        icon="🚇",
        color="#38bdf8",
    ),
    "bus": CategoryConfig(
        key="bus",
        label_tr="Otobüs Durağı & Hat Erişimi",
        weight=0.12,
        fclasses=["bus_stop", "bus_station", "platform"],
        ideal_walk_mins=2.5,
        max_walk_mins=14.0,
        icon="🚌",
        color="#06b6d4",
    ),
    "market": CategoryConfig(
        key="market",
        label_tr="Market, AVM & Pazar Yeri",
        weight=0.18,
        fclasses=[
            "supermarket",
            "convenience",
            "grocery",
            "grocery_store",
            "organic_grocery_store",
            "bakery",
            "greengrocer",
            "produce_store",
            "butcher",
            "butcher_shop",
            "market_place",
            "marketplace",
            "farmers_market",
            "mall",
            "shopping_mall",
            "department_store",
            "deli",
            "dairy",
            "cheese_shop",
            "wholesale",
            "pastry",
            "fishmonger",
            "spices",
        ],
        ideal_walk_mins=3.0,
        max_walk_mins=15.0,
        icon="🛒",
        color="#a855f7",
    ),
    "daily_service": CategoryConfig(
        key="daily_service",
        label_tr="Banka, ATM, Posta & Günlük Hizmet",
        weight=0.10,
        fclasses=[
            "bank",
            "bank_or_credit_union",
            "atm",
            "post_office",
            "freight_and_cargo_service",
            "courier",
            "hairdresser",
            "hair_salon",
            "beauty_salon",
            "laundry",
            "dry_cleaning",
            "tailor",
            "stationery",
            "copyshop",
            "kiosk",
            "fuel",
            "notary",
        ],
        ideal_walk_mins=3.5,
        max_walk_mins=16.0,
        icon="🏦",
        color="#6366f1",
    ),
    "school": CategoryConfig(
        key="school",
        label_tr="Okul & Eğitim Kurumları",
        weight=0.12,
        fclasses=[
            "school",
            "elementary_school",
            "high_school",
            "kindergarten",
            "preschool",
            "day_care_preschool",
            "prep_school",
            "language_school",
            "music_school",
            "specialty_school",
            "university",
            "college",
            "college_university",
            "library",
            "education",
            "place_of_learning",
        ],
        ideal_walk_mins=4.5,
        max_walk_mins=20.0,
        icon="🎓",
        color="#eab308",
    ),
    "health": CategoryConfig(
        key="health",
        label_tr="Hastane, Tıp Merkezi & Klinik",
        weight=0.10,
        fclasses=[
            "hospital",
            "clinic",
            "doctors",
            "doctors_office",
            "dentist",
            "dental_clinic",
            "orthodontics",
            "health_care",
            "diagnostics_imaging_or_lab_service",
            "medical_service_organization",
            "veterinary",
        ],
        ideal_walk_mins=5.0,
        max_walk_mins=22.0,
        icon="🏥",
        color="#ec4899",
    ),
    "pharmacy": CategoryConfig(
        key="pharmacy",
        label_tr="Eczane & Medikal",
        weight=0.08,
        fclasses=[
            "pharmacy",
            "pharmacy_and_drug_store",
            "chemist",
            "medical_supply_store",
            "optician",
        ],
        ideal_walk_mins=3.5,
        max_walk_mins=16.0,
        icon="💊",
        color="#ef4444",
    ),
    "social": CategoryConfig(
        key="social",
        label_tr="Kafe, Restoran & Sosyal Yaşam",
        weight=0.08,
        fclasses=[
            "cafe",
            "coffee_shop",
            "restaurant",
            "turkish_restaurant",
            "casual_eatery",
            "fast_food",
            "fast_food_restaurant",
            "bar",
            "pub",
            "biergarten",
            "food_court",
            "ice_cream",
            "cinema",
            "theatre",
            "arts_centre",
            "community_centre",
        ],
        ideal_walk_mins=3.5,
        max_walk_mins=18.0,
        icon="☕",
        color="#f97316",
    ),
    "green": CategoryConfig(
        key="green",
        label_tr="Park, Yeşil Alan & Spor",
        weight=0.06,
        fclasses=[
            "park",
            "playground",
            "sports_centre",
            "fitness_centre",
            "fitness_station",
            "gym",
            "pitch",
            "dog_park",
            "swimming_pool",
            "garden",
            "forest",
        ],
        ideal_walk_mins=4.0,
        max_walk_mins=18.0,
        icon="🌳",
        color="#10b981",
    ),
}


def score_to_grade(score: float) -> Tuple[str, str]:
    """Return letter grade and descriptive label for a 0-100 PropScore."""
    if score >= 85:
        return "A+", "Çok Yüksek Erişilebilirlik (Prime Konum)"
    elif score >= 75:
        return "A", "Yüksek Erişilebilirlik"
    elif score >= 65:
        return "B", "İyi / Dengeli Konum"
    elif score >= 50:
        return "C", "Orta Erişilebilirlik (Araç Önerilir)"
    else:
        return "D", "Düşük Erişilebilirlik (İzole Konum)"
