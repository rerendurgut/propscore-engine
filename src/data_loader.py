"""Multi-source GIS data loader: Geofabrik SHP + Overture Maps (25k Places & 23k Buildings) + CHECKET Bursa Transit + Overpass."""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import duckdb
import numpy as np
import pandas as pd
import geopandas as gpd
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import Point, LineString, box

from src.config import (
    CATEGORIES,
    EXCLUDED_ROAD_FCLASSES,
    METRIC_CRS,
    WGS84_CRS,
)


def _find_shp(shp_dir: Path, prefix: str) -> Optional[Path]:
    candidates = sorted(shp_dir.glob(f"{prefix}*.shp"))
    return candidates[0] if candidates else None


def _ensure_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if len(gdf) == 0:
        return gdf.set_crs(WGS84_CRS, allow_override=True)
    if gdf.crs is None:
        return gdf.set_crs(WGS84_CRS)
    return gdf.to_crs(WGS84_CRS)


def _has_word(text: str, word: str) -> bool:
    """Check if word/phrase appears with word boundaries or safe delimiters."""
    import re
    return bool(re.search(rf"(?<![a-zçğıöşü0-9]){re.escape(word)}(?![a-zçğıöşü0-9])", text))


def _classify_place(
    name: str,
    brand: str,
    fclass_or_tax: str,
    basic_cat: str,
    fclass_to_cat: Dict[str, str],
) -> Tuple[Optional[str], str]:
    """
    Classify a POI into one of the 9 PropScore categories using taxonomy + Turkish name/brand intelligence.
    Returns (category_key, descriptive_sub_type).
    """
    fc = str(fclass_or_tax or "").strip().lower()
    bc = str(basic_cat or "").strip().lower()
    text = f"{name} {brand}".lower()

    # Global exclusions for non-POI commercial offices / veterinary / irrelevant businesses
    vet_or_pet_words = [
        "veteriner", "veterinary", "pati ", "patiler", "petshop", "pet shop",
        "pet klinik", "pet clinic", "hayvan hastanesi", "evcil hayvan", "köpek eğitim",
    ]
    if fc in ("veterinarian", "veterinary_service", "pet_store", "pet_groomer", "animal_shelter") or bc in (
        "veterinary_service", "pet_services", "pet_store"
    ) or any(w in text for w in vet_or_pet_words) or _has_word(text, "vet"):
        return None, fc

    ignore_business_words = [
        "emlak", "gayrimenkul", "inşaat", "yapı denetim", "mimarlık", "mühendislik",
        "sigorta", "osgb", "iş sağlığı ve güvenliği", "psikoteknik", "hediyelik",
        "perde", "sineklik", "mobilya", "aydınlatma", "elektrik", "nalbur", "boya",
        "oto yıkama", "oto lastik", "oto tamir", "ekspertiz", "galeri", "rent a car",
    ]
    if any(w in text for w in ignore_business_words):
        return None, fc

    # 1. Explicit Pharmacy check first (so 'Korupark Eczanesi' doesn't become 'park' or 'mall')
    if (
        fc in ("pharmacy", "pharmacy_and_drug_store", "chemist")
        or bc == "pharmacy_and_drug_store"
        or "eczane" in text
        or "pharmacy" in text
    ):
        return "pharmacy", "Eczane"

    # 2. Explicit Market / AVM / Pazar / Fırın / Kasap / Manav check
    if "tarım" not in text and "yapı market" not in text and "oto market" not in text:
        if (
            fc in ("shopping_mall", "mall", "department_store")
            or bc == "shopping_mall"
            or any(k in text for k in ["avm", "alışveriş merkezi", "korupark", "marka avm", "nilpark", "parkora", "özdilek", "ozdilek"])
        ):
            return "market", "AVM"

        if (
            fc in ("market_place", "marketplace", "farmers_market")
            or any(k in text for k in ["semt pazarı", "pazar alanı", "kapalı pazar", "köylü pazarı"])
        ):
            return "market", "Semt Pazarı"

        if (
            fc in ("bakery", "pastry")
            or any(k in text for k in ["fırın", "ekmek", "unlu mamül", "taş fırın"])
        ):
            return "market", "Fırın / Unlu Mamül"

        if (
            fc in ("butcher", "butcher_shop", "deli", "cheese_shop", "fishmonger")
            or any(k in text for k in ["kasap", "et galerisi", "şarküteri", "mandıra"])
        ):
            return "market", "Kasap / Şarküteri"

        if (
            fc in ("greengrocer", "produce_store")
            or _has_word(text, "manav")
            or "manavı" in text
        ):
            return "market", "Manav"

        chain_and_market_words = [
            "migros", "a101", "a-101", "şok market", "sok market", "carrefour",
            "file market", "özhan", "ozhan", "onur market", "onur hiper", "furpa",
            "seyhanlar", "seyhan ekspres", "metro gross", "tarım kredi", "süpermarket",
            "supermarket", "hipermarket", "bakkal", "market",
        ]
        if (
            any(k in text for k in chain_and_market_words)
            or _has_word(text, "bim")
            or _has_word(text, "şok")
            or fc in ("supermarket", "convenience", "grocery", "grocery_store", "organic_grocery_store")
            or bc == "food_and_beverage_store"
        ):
            return "market", "Süpermarket / Market"

    # 3. Explicit School & Education check (excluding driving schools, sports clubs, Quran courses, security booths)
    school_exclude = [
        "sürücü", "direksiyon", "futbol", "okçuluk", "tenis", "yüzme", "cimnastik",
        "basketbol", "voleybol", "dans", "pilates", "yoga", "spor kulübü", "spor akademi",
        "kuran kursu", "kur'an kursu", "güvenlik", "art studio", "sanat atölyesi",
        "müzik kursu", "piyano", "gitar", "bale",
    ]
    if fc not in ("driving_school", "gym", "sports_club_and_league") and not any(ex in text for ex in school_exclude):
        if fc in ("university", "college", "college_university") or any(k in text for k in ["üniversite", "fakülte", "yüksekokul", "kampüs"]):
            return "school", "Üniversite / Kampüs"
        if fc == "high_school" or "lise" in text:
            return "school", "Lise"
        if "kolej" in text or fc == "private_school" or ("özel " in text and ("okul" in text or "okulları" in text)):
            return "school", "Kolej / Özel Okul"
        if fc in ("elementary_school", "middle_school") or any(k in text for k in ["ilkokul", "ortaokul", "ilköğretim"]):
            return "school", "İlkokul / Ortaokul"
        if fc in ("kindergarten", "preschool", "day_care_preschool") or any(k in text for k in ["anaokulu", "kreş", "gündüz bakımevi"]):
            return "school", "Anaokulu / Kreş"
        if fc == "library" or "kütüphane" in text or "library" in text:
            return "school", "Kütüphane"
        if (
            fc in ("school", "vocational_and_technical_school", "special_education_school", "language_school", "prep_school")
            or bc in ("preschool", "elementary_school")
            or any(k in text for k in ["okul", "okulları", "dershane", "etüt merkezi", "dil okulu", "meslek okulu"])
        ):
            return "school", "Okul / Eğitim Kurumu"

    # 4. Explicit Health (Hospital, ASM, Medical Center, Polyclinic, Dental, Doctor)
    health_exclude = [
        "güzellik", "estetik", "epilasyon", "saç ekim", "solaryum", "tırnak", "make up",
        "makyaj", "işitme cihaz", "optik", "gözlük", "medikal", "protez", "ortez",
        "diyetisyen", "beslenme", "psikolog", "psikolojik danışmanlık", "terapi merkezi",
        "manuel terapi", "manuelterapi", "masaj", "spa", "pilates", "yoga",
    ]
    if not any(ex in text for ex in health_exclude):
        if (
            "aile sağlığı" in text
            or "sağlık ocağı" in text
            or _has_word(text, "asm")
            or "toplum sağlığı" in text
        ):
            return "health", "Aile Sağlığı Mrk. (ASM)"

        if (
            fc == "hospital"
            or "hastane" in text
            or "hospital" in text
            or "fakültesi hastanesi" in text
        ):
            return "health", "Hastane"

        if (
            fc in ("dental_clinic", "dentist", "orthodontics")
            or bc == "dental_clinic"
            or "ağız ve diş" in text
            or "diş kliniği" in text
            or "diş polikliniği" in text
            or "diş hekimi" in text
            or "dental" in text
            or _has_word(text, "dent")
        ):
            return "health", "Diş Kliniği / Polikliniği"

        if (
            fc in ("clinic", "outpatient_care_facility", "medical_center", "urgent_care_clinic", "public_health_clinic")
            or any(k in text for k in ["tıp merkezi", "tıp merkez", "poliklinik", "polikliniği", "sağlık merkezi", "diyaliz"])
        ):
            return "health", "Tıp Merkezi / Poliklinik"

        if (
            fc in ("doctors", "doctors_office", "obstetrics_and_gynecology", "pediatrics", "dermatology", "cardiology", "ophthalmologist")
            or any(k in text for k in ["muayenehane", "uzm. dr", "op. dr", "prof. dr", "doç. dr", "dr. "])
        ):
            return "health", "Doktor / Uzman Klinik"

    # 5. Explicit Daily Services (Bank, ATM, PTT/Post, Cargo, Notary, Dry Cleaning, Stationery, Barber, Fuel)
    if (
        fc == "atm"
        or bc == "atm"
        or _has_word(text, "atm")
        or "bankamatik" in text
        or "paramatik" in text
    ):
        return "daily_service", "ATM / Bankamatik"

    bank_keywords = [
        "banka", "garanti bbva", "iş bankası", "ziraat bank", "yapı kredi", "akbank",
        "vakıfbank", "halkbank", "qnb", "denizbank", "teb ", "kuveyt türk", "albaraka",
        "ing bank", "odeabank", "fibabanka", "şekerbank", "anadolubank", "vakıf katılım",
        "ziraat katılım", "emlak katılım",
    ]
    if fc in ("bank", "bank_or_credit_union") or bc == "bank_or_credit_union" or any(k in text for k in bank_keywords):
        return "daily_service", "Banka Şubesi"

    if fc == "post_office" or _has_word(text, "ptt") or "postane" in text:
        return "daily_service", "PTT / Posta"

    if fc == "freight_and_cargo_service" or any(k in text for k in ["yurtiçi kargo", "aras kargo", "mng kargo", "sürat kargo", "ups kargo", "dhl", "ptt kargo", "kargo şube", "kargo "]):
        return "daily_service", "Kargo Şubesi"

    if fc == "notary" or "noter" in text:
        return "daily_service", "Noter"

    if fc in ("stationery", "copyshop") or any(k in text for k in ["kırtasiye", "fotokopi", "ozalit"]):
        return "daily_service", "Kırtasiye / Fotokopi"

    if fc in ("laundry", "dry_cleaning", "tailor") or any(k in text for k in ["kuru temizleme", "terzi", "çamaşırhane", "ütü evi"]):
        return "daily_service", "Kuru Temizleme / Terzi"

    if fc in ("hairdresser", "hair_salon", "barber") or any(k in text for k in ["kuaför", "berber"]):
        return "daily_service", "Kuaför / Berber"

    if fc in ("fuel", "gas_station", "electric_vehicle_charging_station") or any(k in text for k in ["opet", "shell", "petrol ofisi", "bp ", "totalenergies", "aytemiz", "akaryakıt"]):
        return "daily_service", "Akaryakıt / Şarj"

    # 6. Social (Cafe, Restaurant, Fast Food, Cinema, Culture)
    if fc in ("cinema", "theatre", "arts_centre", "community_centre") or any(k in text for k in ["sinema", "tiyatro", "kültür merkez", "sanat merkez"]):
        return "social", "Kültür & Sinema"

    if fc in ("cafe", "coffee_shop", "ice_cream") or bc in ("cafe", "coffee_shop") or any(k in text for k in ["kafe", "cafe", "kahve", "coffee", "starbucks", "espressolab", "mado", "pastane", "muhallebi", "çay bahçesi"]):
        return "social", "Kafe & Pastane"

    social_rest_keywords = [
        "restoran", "restaurant", "lokanta", "kebap", "köfte", "döner", "pide",
        "lahmacun", "pizza", "burger", "bistro", "meyhane", "pub", "iskender", "tantuni",
    ]
    if any(k in text for k in social_rest_keywords) or fc in (
        "restaurant", "turkish_restaurant", "casual_eatery", "fast_food", "fast_food_restaurant", "bar", "pub", "food_court"
    ) or bc in ("restaurant", "casual_eatery", "fast_food_restaurant", "bar"):
        return "social", "Restoran & Yeme-İçme"

    # 7. Green & Sports (Park, Playground, Gym, Sports, Pool)
    if fc in ("park", "garden", "forest", "dog_park") or bc == "park" or any(k in text for k in ["parkı", "parki", "koruluğu", "mesire", "kent ormanı", "botanik"]):
        return "green", "Park & Yeşil Alan"

    if fc == "playground" or "çocuk parkı" in text or "oyun alanı" in text:
        return "green", "Çocuk Oyun Alanı"

    if fc in ("sports_centre", "fitness_centre", "fitness_station", "gym", "pitch", "swimming_pool") or bc == "gym" or any(k in text for k in ["spor salonu", "fitness", "macfit", "yüzme havuzu", "halı saha", "tenis kortu", "spor tesisi"]):
        return "green", "Spor & Fitness"

    return None, fc


def _load_overture_places(
    project_root: Path,
    padded_bbox: Tuple[float, float, float, float],
    fclass_to_cat: Dict[str, str],
) -> List[dict]:
    """Load and classify POIs from Overture Maps local parquet (data/overture_nilufer_places.parquet)."""
    pq_path = project_root / "data" / "overture_nilufer_places.parquet"
    if not pq_path.exists():
        return []

    min_x, min_y, max_x, max_y = padded_bbox
    con = duckdb.connect()
    df = con.execute(
        f"""
        SELECT
            id,
            names['primary'] AS name,
            brand['names']['primary'] AS brand_name,
            basic_category,
            taxonomy['primary'] AS tax_primary,
            confidence,
            operating_status,
            bbox['xmin'] AS lon,
            bbox['ymin'] AS lat
        FROM read_parquet('{pq_path.as_posix()}')
        WHERE (operating_status IS NULL OR operating_status != 'closed')
          AND bbox['xmin'] BETWEEN {min_x} AND {max_x}
          AND bbox['ymin'] BETWEEN {min_y} AND {max_y}
        """
    ).df()

    rows: List[dict] = []
    for r in df.itertuples():
        name_str = str(r.name or "").strip()
        brand_str = str(r.brand_name or "").strip()
        tax_str = str(r.tax_primary or "").strip()
        bc_str = str(r.basic_category or "").strip()

        cat, norm_fc = _classify_place(name_str, brand_str, tax_str, bc_str, fclass_to_cat)
        if not cat or cat in ("metro", "bus"):
            continue

        disp_name = name_str or brand_str or norm_fc.replace("_", " ").title()
        rows.append(
            {
                "osm_id": f"ovt_{r.id[:12]}",
                "fclass": norm_fc,
                "name": disp_name,
                "category": cat,
                "extra_info": brand_str,
                "geometry": Point(float(r.lon), float(r.lat)),
            }
        )
    return rows


def _load_overpass_pois(
    project_root: Path,
    padded_bbox: Tuple[float, float, float, float],
    fclass_to_cat: Dict[str, str],
) -> List[dict]:
    """Parse cached Overpass JSON files (overpass_nilufer_pois.json & overpass_nilufer_extra.json)."""
    rows = []
    min_x, min_y, max_x, max_y = padded_bbox

    for fname in ["overpass_nilufer_pois.json", "overpass_nilufer_extra.json"]:
        fpath = project_root / "data" / fname
        if not fpath.exists():
            continue
        try:
            raw = json.loads(fpath.read_text(encoding="utf-8"))
        except Exception:
            continue

        for el in raw.get("elements", []):
            tags = el.get("tags", {})
            if not tags:
                continue
            lat = el.get("lat") or (el.get("center", {}) or {}).get("lat")
            lon = el.get("lon") or (el.get("center", {}) or {}).get("lon")
            if lat is None or lon is None:
                continue
            if not (min_x <= lon <= max_x and min_y <= lat <= max_y):
                continue

            name = tags.get("name") or tags.get("brand") or tags.get("operator") or ""
            brand = tags.get("brand") or ""
            fc = (
                tags.get("shop")
                or tags.get("amenity")
                or tags.get("healthcare")
                or tags.get("leisure")
                or tags.get("office")
                or ""
            )

            cat, norm_fc = _classify_place(name, brand, fc, "", fclass_to_cat)
            if not cat or cat in ("metro", "bus"):
                continue

            display_name = str(name).strip() if str(name).strip() else norm_fc.replace("_", " ").title()
            rows.append(
                {
                    "osm_id": f"ovp_{el.get('id', len(rows))}",
                    "fclass": norm_fc,
                    "name": display_name,
                    "category": cat,
                    "extra_info": brand,
                    "geometry": Point(float(lon), float(lat)),
                }
            )
    return rows


def _extract_building_pois(buildings_wgs: gpd.GeoDataFrame, fclass_to_cat: Dict[str, str]) -> List[dict]:
    """Extract major supermarkets, malls, hospitals, schools, pharmacies, and banks tagged on buildings."""
    rows = []
    if len(buildings_wgs) == 0:
        return rows

    bldg_m = buildings_wgs.to_crs(METRIC_CRS)
    centroids_wgs = gpd.GeoSeries(bldg_m.geometry.centroid, crs=METRIC_CRS).to_crs(WGS84_CRS)

    for idx, row in buildings_wgs.iterrows():
        raw_name = row.get("name")
        btype = str(row.get("type") or "").lower()
        name_str = str(raw_name).strip() if pd.notnull(raw_name) else ""
        if not name_str and btype in ("", "building", "apartments", "residential", "house", "yes", "roof", "industrial"):
            continue

        cat, norm_fc = _classify_place(name_str, "", btype, "", fclass_to_cat)
        if cat and cat not in ("metro", "bus"):
            rows.append(
                {
                    "osm_id": f"bpoi_{row.get('osm_id', idx)}",
                    "fclass": norm_fc,
                    "name": name_str if name_str else norm_fc.title(),
                    "category": cat,
                    "extra_info": "Bina İçi Kurum/İşletme",
                    "geometry": centroids_wgs.iloc[idx],
                }
            )
    return rows


def _load_checket_transit(
    project_root: Path,
    padded_bbox: Tuple[float, float, float, float],
) -> Tuple[List[dict], List[dict], Optional[gpd.GeoDataFrame], Optional[gpd.GeoDataFrame]]:
    """Load official BursaRay Metro Stations, BURULAŞ Bus Stops (with route numbers), and Mahalle Polygons."""
    checket_dir = project_root / "data" / "checket"
    if not checket_dir.exists():
        alt = Path("/Users/receperendurgut/Desktop/CHECKET")
        if alt.exists():
            checket_dir = alt

    metro_rows: List[dict] = []
    bus_rows: List[dict] = []
    corridors_gdf: Optional[gpd.GeoDataFrame] = None
    mahalle_gdf: Optional[gpd.GeoDataFrame] = None

    if not checket_dir.exists():
        return metro_rows, bus_rows, corridors_gdf, mahalle_gdf

    min_x, min_y, max_x, max_y = padded_bbox

    train_file = checket_dir / "bursa_train_station.gpkg"
    if train_file.exists():
        tr = _ensure_wgs84(gpd.read_file(train_file))
        tr = tr.cx[min_x:max_x, min_y:max_y].copy()
        for idx, r in tr.iterrows():
            st_name = str(r.get("name") or "BursaRay İstasyonu").strip()
            if "İstasyon" not in st_name and "Metro" not in st_name:
                st_name = f"BursaRay {st_name} İstasyonu"
            metro_rows.append(
                {
                    "osm_id": f"metro_{r.get('osm_id', idx)}",
                    "fclass": "BursaRay Metro İstasyonu",
                    "name": st_name,
                    "category": "metro",
                    "extra_info": "BursaRay Metro Hattı",
                    "geometry": r.geometry.centroid,
                }
            )

    bus_file = checket_dir / "bursa_otobus_ilce_mahalle.gpkg"
    if bus_file.exists():
        bs = _ensure_wgs84(gpd.read_file(bus_file))
        bs = bs.cx[min_x:max_x, min_y:max_y].copy()
        if len(bs) > 0:
            grouped = (
                bs.groupby("durak_id")
                .agg(
                    durak_adi=("durak_adi", "first"),
                    hatlar=(
                        "hat_adi",
                        lambda s: ", ".join(sorted(set(str(x).strip() for x in s if pd.notnull(x) and str(x).strip()))),
                    ),
                    geometry=("geometry", "first"),
                )
                .reset_index()
            )
            for _, r in grouped.iterrows():
                d_name = str(r["durak_adi"] or f"Durak #{r['durak_id']}").strip().title()
                hatlar_str = str(r["hatlar"] or "").strip()
                bus_rows.append(
                    {
                        "osm_id": f"durak_{r['durak_id']}",
                        "fclass": "BURULAŞ Otobüs Durağı",
                        "name": f"{d_name} Durağı",
                        "category": "bus",
                        "extra_info": hatlar_str,
                        "geometry": r["geometry"].centroid,
                    }
                )

    corr_file = checket_dir / "bursa_yeni_sistem_metric.gpkg"
    if corr_file.exists():
        cg = _ensure_wgs84(gpd.read_file(corr_file))
        cg = cg.cx[min_x:max_x, min_y:max_y].copy()
        if len(cg) > 0:
            corridors_gdf = cg[["hat_kodu", "hat_adi", "tip", "metro_istasyonu", "geometry"]].copy()

    ilce_file = checket_dir / "Bursa_ilce.gpkg"
    if ilce_file.exists():
        mg = _ensure_wgs84(gpd.read_file(ilce_file))
        mg = mg.cx[min_x:max_x, min_y:max_y].copy()
        if len(mg) > 0:
            mahalle_gdf = mg[["name", "geometry"]].copy()

    return metro_rows, bus_rows, corridors_gdf, mahalle_gdf


def _merge_overture_buildings(
    osm_buildings: gpd.GeoDataFrame,
    project_root: Path,
    bbox: Tuple[float, float, float, float],
) -> gpd.GeoDataFrame:
    """Supplement OSM buildings with missing buildings from Overture Maps (Microsoft/Google AI footprints)."""
    pq_path = project_root / "data" / "overture_nilufer_buildings.parquet"
    if not pq_path.exists():
        return osm_buildings

    min_x, min_y, max_x, max_y = bbox
    con = duckdb.connect()
    df = con.execute(
        f"""
        SELECT
            id,
            names['primary'] AS name,
            subtype,
            class AS bclass,
            geometry
        FROM read_parquet('{pq_path.as_posix()}')
        WHERE bbox['xmin'] >= {min_x} AND bbox['xmax'] <= {max_x}
          AND bbox['ymin'] >= {min_y} AND bbox['ymax'] <= {max_y}
        """
    ).df()
    if len(df) == 0:
        return osm_buildings

    geoms = shapely.from_wkb([bytes(b) for b in df["geometry"]])
    ov_gdf = gpd.GeoDataFrame(
        {
            "osm_id": [f"ovb_{i}" for i in range(len(df))],
            "code": 1500,
            "fclass": "building",
            "name": df["name"].values,
            "type": df["bclass"].fillna(df["subtype"]).fillna("residential").values,
        },
        geometry=geoms,
        crs=WGS84_CRS,
    )

    # Keep only Overture buildings whose centroid is > 12m away from any existing OSM building centroid
    osm_m = osm_buildings.to_crs(METRIC_CRS)
    ov_m = ov_gdf.to_crs(METRIC_CRS)
    osm_xy = np.column_stack([osm_m.geometry.centroid.x.values, osm_m.geometry.centroid.y.values])
    ov_xy = np.column_stack([ov_m.geometry.centroid.x.values, ov_m.geometry.centroid.y.values])

    dists, _ = cKDTree(osm_xy).query(ov_xy, k=1)
    new_mask = dists > 12.0
    added_buildings = ov_gdf[new_mask].copy()
    if len(added_buildings) > 0:
        merged = gpd.GeoDataFrame(
            pd.concat([osm_buildings, added_buildings], ignore_index=True),
            crs=WGS84_CRS,
        )
        print(f"  + Overture AI Bina Katmanından {len(added_buildings):,} eksik bina eklendi!")
        return merged
    return osm_buildings


def load_geofabrik_bbox(
    shp_dir: str | Path,
    bbox: Tuple[float, float, float, float],
) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, Dict[str, gpd.GeoDataFrame]]:
    """
    Load buildings (OSM + Overture AI), walkable roads, 9-category multi-source POIs
    (CHECKET Bus/Metro + Overture 25k Places + Overpass + Geofabrik), and vector basemap layers.
    """
    shp_path = Path(shp_dir).expanduser().resolve()
    project_root = Path(__file__).resolve().parent.parent
    if not shp_path.exists():
        raise FileNotFoundError(f"SHP klasörü bulunamadı: {shp_path}")

    pad = 0.010
    padded_bbox = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)

    # 1. Load Buildings (OSM + Overture AI missing buildings)
    bldg_file = _find_shp(shp_path, "gis_osm_buildings")
    if not bldg_file:
        raise FileNotFoundError(f"Bina katmanı bulunamadı: {shp_path}")
    print(f"[1/5] Binalar okunuyor ({bldg_file.name} + Overture AI Footprints)...")
    buildings = _ensure_wgs84(gpd.read_file(bldg_file, bbox=bbox))
    buildings = buildings[buildings.geometry.notnull() & ~buildings.geometry.is_empty].copy()
    buildings.reset_index(drop=True, inplace=True)
    buildings = _merge_overture_buildings(buildings, project_root, bbox)

    # 2. Load Roads
    road_file = _find_shp(shp_path, "gis_osm_roads")
    if not road_file:
        raise FileNotFoundError(f"Yol katmanı bulunamadı: {shp_path}")
    print(f"[2/5] Sokak ve bulvar ağı okunuyor ({road_file.name})...")
    all_roads = _ensure_wgs84(gpd.read_file(road_file, bbox=padded_bbox))
    all_roads = all_roads[all_roads.geometry.notnull() & ~all_roads.geometry.is_empty].copy()
    all_roads.reset_index(drop=True, inplace=True)

    if "fclass" in all_roads.columns:
        walk_roads = all_roads[~all_roads["fclass"].isin(EXCLUDED_ROAD_FCLASSES)].copy()
    else:
        walk_roads = all_roads.copy()
    walk_roads.reset_index(drop=True, inplace=True)

    # 3. Load CHECKET Bursa Official Transit (Metro + Bus Stops with Passing Lines + Mahalle Polygons)
    print("[3/5] CHECKET Bursa Resmi Metro İstasyonları, Otobüs Durakları & Hatları yükleniyor...")
    metro_rows, bus_rows, corridors_gdf, mahalle_gdf = _load_checket_transit(project_root, padded_bbox)

    # 4. Load 9-Category POIs (Overture 25k Places + Overpass + Geofabrik + Building Landmarks)
    print("[4/5] 9 Kategori POI Birleştiriliyor (Overture Maps 25.153 İşletme + Overpass + Geofabrik)...")
    fclass_to_cat: Dict[str, str] = {}
    for cat_key, cfg in CATEGORIES.items():
        for fc in cfg.fclasses:
            fclass_to_cat[fc] = cat_key

    overture_rows = _load_overture_places(project_root, padded_bbox, fclass_to_cat)
    overpass_rows = _load_overpass_pois(project_root, padded_bbox, fclass_to_cat)
    bldg_poi_rows = _extract_building_pois(buildings, fclass_to_cat)

    poi_prefixes = [
        "gis_osm_pois_free",
        "gis_osm_pois_a_free",
        "gis_osm_transport_free",
        "gis_osm_transport_a_free",
        "gis_osm_landuse_a_free",
    ]
    shp_poi_rows: List[dict] = []
    for prefix in poi_prefixes:
        fpath = _find_shp(shp_path, prefix)
        if fpath is not None:
            gdf = _ensure_wgs84(gpd.read_file(fpath, bbox=padded_bbox))
            if len(gdf) == 0 or "fclass" not in gdf.columns:
                continue
            gdf_m = gdf.to_crs(METRIC_CRS)
            pts_wgs = gpd.GeoSeries(gdf_m.geometry.centroid, crs=METRIC_CRS).to_crs(WGS84_CRS)
            for idx_r, r in enumerate(gdf.itertuples()):
                fc = str(getattr(r, "fclass", "") or "")
                raw_n = getattr(r, "name", None)
                name_s = str(raw_n).strip() if pd.notnull(raw_n) else ""
                cat, norm_fc = _classify_place(name_s, "", fc, "", fclass_to_cat)
                if not cat:
                    continue
                if cat in ("metro", "bus") and (len(metro_rows) > 0 and len(bus_rows) > 0):
                    continue
                disp_n = name_s if name_s else norm_fc.replace("_", " ").title()
                shp_poi_rows.append(
                    {
                        "osm_id": str(getattr(r, "osm_id", f"shp_{idx_r}")),
                        "fclass": norm_fc,
                        "name": disp_n,
                        "category": cat,
                        "extra_info": "",
                        "geometry": pts_wgs.iloc[idx_r],
                    }
                )

    all_poi_rows = metro_rows + bus_rows + overture_rows + overpass_rows + bldg_poi_rows + shp_poi_rows
    if all_poi_rows:
        pois = gpd.GeoDataFrame(all_poi_rows, crs=WGS84_CRS)
        # Spatial deduplication within 20m grid for same category + normalized name
        pois_m = pois.to_crs(METRIC_CRS)
        pois["_rx"] = (pois_m.geometry.x / 20.0).round().astype(int)
        pois["_ry"] = (pois_m.geometry.y / 20.0).round().astype(int)
        pois["_norm_name"] = pois["name"].astype(str).str.lower().str.strip()
        pois = (
            pois.drop_duplicates(subset=["category", "_norm_name", "_rx", "_ry"])
            .drop(columns=["_rx", "_ry", "_norm_name"])
            .reset_index(drop=True)
        )
    else:
        pois = gpd.GeoDataFrame(columns=["osm_id", "fclass", "name", "category", "extra_info", "geometry"], crs=WGS84_CRS)

    # 5. Load Context / Vector Basemap Layers & Official Mahalle Assignment
    print("[5/5] Özel Vektör Harita katmanları ve Resmi Mahalle sınırları eşleştiriliyor...")
    context_layers: Dict[str, gpd.GeoDataFrame] = {
        "roads": all_roads[["osm_id", "fclass", "name", "geometry"]].copy()
    }
    if corridors_gdf is not None:
        context_layers["bus_corridors"] = corridors_gdf
    if mahalle_gdf is not None:
        context_layers["mahalle_boundaries"] = mahalle_gdf

    lu_file = _find_shp(shp_path, "gis_osm_landuse_a_free")
    if lu_file:
        lu = _ensure_wgs84(gpd.read_file(lu_file, bbox=padded_bbox))
        keep_lu = {"park", "grass", "forest", "residential", "commercial", "retail", "industrial", "recreation_ground"}
        if "fclass" in lu.columns:
            lu = lu[lu["fclass"].isin(keep_lu)].copy()
        context_layers["landuse"] = lu[["osm_id", "fclass", "name", "geometry"]].copy()

    rw_file = _find_shp(shp_path, "gis_osm_railways_free")
    if rw_file:
        rw = _ensure_wgs84(gpd.read_file(rw_file, bbox=padded_bbox))
        context_layers["railways"] = rw[["osm_id", "fclass", "name", "geometry"]].copy()

    ww_file = _find_shp(shp_path, "gis_osm_waterways_free")
    if ww_file:
        ww = _ensure_wgs84(gpd.read_file(ww_file, bbox=padded_bbox))
        context_layers["waterways"] = ww[["osm_id", "fclass", "name", "geometry"]].copy()

    wt_file = _find_shp(shp_path, "gis_osm_water_a_free")
    if wt_file:
        wt = _ensure_wgs84(gpd.read_file(wt_file, bbox=padded_bbox))
        context_layers["water"] = wt[["osm_id", "fclass", "name", "geometry"]].copy()

    pl_file = _find_shp(shp_path, "gis_osm_places_free")
    if pl_file:
        pl = _ensure_wgs84(gpd.read_file(pl_file, bbox=padded_bbox))
        pl = pl[pl["name"].notnull()].copy()
        context_layers["places"] = pl[["osm_id", "fclass", "name", "geometry"]].copy()

    if mahalle_gdf is not None and len(mahalle_gdf) > 0 and len(buildings) > 0:
        bldg_m = buildings.to_crs(METRIC_CRS)
        bldg_pts = gpd.GeoDataFrame(geometry=gpd.GeoSeries(bldg_m.geometry.centroid, crs=METRIC_CRS).to_crs(WGS84_CRS))
        joined = gpd.sjoin(bldg_pts, mahalle_gdf[["name", "geometry"]], how="left", predicate="within")
        joined = joined[~joined.index.duplicated(keep="first")]
        buildings["mahalle"] = joined["name"].fillna("Nilüfer Mah.").values
    else:
        buildings["mahalle"] = "Nilüfer Mah."

    cat_summary = pois["category"].value_counts().to_dict() if len(pois) > 0 else {}
    print(
        f"✓ Çok Kaynaklı (Overture + CHECKET + OSM) Veri Yüklendi:\n"
        f"  • Toplam Bina       : {len(buildings):,} gerçek bina poligonu\n"
        f"  • Yürünebilir Sokak : {len(walk_roads):,} sokak segmenti\n"
        f"  • Toplam Hizmet/POI : {len(pois):,} nokta\n"
        f"  • 9 Kategori Detayı : {cat_summary}"
    )
    return buildings, walk_roads, pois, context_layers


def generate_nilufer_demo_data(
    bbox: Tuple[float, float, float, float] = (28.952, 40.203, 28.996, 40.235),
    seed: int = 42,
) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame, Dict[str, gpd.GeoDataFrame]]:
    """Fallback synthetic generator if SHP folder is absent."""
    min_x, min_y, max_x, max_y = bbox
    xs = np.linspace(min_x, max_x, 10)
    ys = np.linspace(min_y, max_y, 8)
    road_geoms = [LineString([(xs[j], y), (xs[j + 1], y)]) for y in ys for j in range(len(xs) - 1)]
    roads = gpd.GeoDataFrame(
        {"osm_id": [f"r_{k}" for k in range(len(road_geoms))], "fclass": ["residential"] * len(road_geoms), "name": ["Sokak"] * len(road_geoms), "geometry": road_geoms},
        crs=WGS84_CRS,
    )
    cx, cy = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
    buildings = gpd.GeoDataFrame(
        [{"osm_id": "1001", "fclass": "building", "name": "Nilüfer Konutları", "type": "apartments", "mahalle": "İhsaniye Mahallesi", "geometry": box(cx - 0.0002, cy - 0.00015, cx + 0.0002, cy + 0.00015)}],
        crs=WGS84_CRS,
    )
    pois = gpd.GeoDataFrame(
        [
            {"osm_id": f"p_{k}", "fclass": k, "name": cfg.label_tr, "category": k, "extra_info": "", "geometry": Point(cx + 0.001, cy)}
            for k, cfg in CATEGORIES.items()
        ],
        crs=WGS84_CRS,
    )
    return buildings, roads, pois, {"roads": roads}
