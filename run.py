#!/usr/bin/env python3
"""
PropScore CLI - Bursa Nilüfer & Türkiye Geneli Gayrimenkul Konum Zekası Motoru.
"""

import argparse
import time
from pathlib import Path

from src.config import REGIONS
from src.data_loader import generate_nilufer_demo_data, load_geofabrik_bbox
from src.network_engine import compute_network_accessibility
from src.scorer import compute_propscores
from src.exporter import export_interactive_web_map, export_qgis_geopackage


def _auto_detect_shp_dir() -> str | None:
    """Automatically find turkey-*-free folder in current workspace if present."""
    root = Path(__file__).resolve().parent
    candidates = sorted(root.glob("turkey-*-free*"))
    for c in candidates:
        if c.is_dir() and any(c.glob("gis_osm_buildings*.shp")):
            return str(c)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="PropScore: Yol Ağı Tabanlı Gayrimenkul Erişilebilirlik & Konum Skoru Motoru"
    )
    parser.add_argument(
        "--shp-dir",
        type=str,
        default=None,
        help="Geofabrik Türkiye SHP dosyalarının bulunduğu klasör yolu (varsayılan: otomatik algılanır)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="nilufer_fsm",
        choices=list(REGIONS.keys()),
        help="Analiz edilecek pilot bölge (varsayılan: nilufer_fsm)",
    )
    parser.add_argument(
        "--bbox",
        type=float,
        nargs=4,
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        default=None,
        help="Özel koordinat kutusu (EPSG:4326)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="SHP klasörü olmadan örnek veriyle çalıştır",
    )
    parser.add_argument(
        "--output-gpkg",
        type=str,
        default="output/nilufer_propscore.gpkg",
        help="Çıktı QGIS GeoPackage (.gpkg) dosya yolu",
    )
    parser.add_argument(
        "--output-html",
        type=str,
        default="docs/index.html",
        help="Çıktı İnteraktif Web Haritası (.html) dosya yolu",
    )

    args = parser.parse_args()
    t0 = time.time()

    reg_info = REGIONS[args.region]
    bbox = tuple(args.bbox) if args.bbox else reg_info["bbox"]
    region_title = reg_info["name"] if not args.bbox else f"Özel Bölge {bbox}"

    shp_dir = args.shp_dir or _auto_detect_shp_dir()

    print("=" * 76)
    print(f"🚀 PROPSCORE ENGINE BAŞLATILIYOR | Bölge: {region_title}")
    print(f"📍 Koordinat Sınırı (BBOX): {bbox}")
    if shp_dir and not args.demo:
        print(f"📂 Veri Kaynağı (SHP): {shp_dir}")
    print("=" * 76)

    if shp_dir and not args.demo:
        buildings, walk_roads, pois, context_layers = load_geofabrik_bbox(shp_dir, bbox=bbox)
    else:
        buildings, walk_roads, pois, context_layers = generate_nilufer_demo_data(bbox=bbox)

    print("\n[Ağ Analizi] Sokak grafı üzerinden binaların gerçek yürüme mesafeleri hesaplanıyor...")
    bldg_access = compute_network_accessibility(buildings, walk_roads, pois)

    print("[Skorlama] Çok kriterli gayrimenkul erişilebilirlik indeksleri (0-100) hesaplanıyor...")
    bldg_scored = compute_propscores(bldg_access)

    avg_s = bldg_scored["propscore"].mean()
    max_s = bldg_scored["propscore"].max()
    min_s = bldg_scored["propscore"].min()
    grade_counts = bldg_scored["grade"].value_counts().to_dict()

    print("\n" + "-" * 76)
    print(f"📊 {region_title.upper()} ANALİZ ÖZETİ")
    print("-" * 76)
    print(f"  • Toplam Analiz Edilen Gerçek Bina : {len(bldg_scored):,}")
    print(f"  • Bölge Ortalama PropScore         : {avg_s:.1f} / 100")
    print(f"  • En Yüksek / En Düşük Skor        : {max_s:.1f} / {min_s:.1f}")
    print(f"  • Sınıf Dağılımı                   : {grade_counts}")
    print("-" * 76 + "\n")

    gpkg_path = export_qgis_geopackage(
        bldg_scored,
        walk_roads,
        pois,
        context_layers=context_layers,
        output_gpkg=args.output_gpkg,
    )
    html_path = export_interactive_web_map(
        bldg_scored,
        pois,
        context_layers=context_layers,
        region_title=region_title,
        output_html=args.output_html,
    )

    elapsed = time.time() - t0
    print(f"\n✅ İşlem {elapsed:.2f} saniyede tamamlandı!")
    print(f"   1) QGIS Katmanı : {gpkg_path}")
    print(f"   2) Web Haritası : {html_path}")


if __name__ == "__main__":
    main()
