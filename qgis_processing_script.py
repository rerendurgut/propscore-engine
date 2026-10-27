"""
PyQGIS Processing Toolbox Script: PropScore Gayrimenkul Erişilebilirlik Motoru.

QGIS İçinde Kullanım:
  1. QGIS -> Processing (İşlem) -> Toolbox (Araç Kutusu) panelini açın.
  2. Üstteki Python ikonuna tıklayıp 'Add Script to Toolbox...' seçeneğini seçin.
  3. Bu dosyayı (qgis_processing_script.py) seçin.
  4. 'PropScore -> Bina Bazlı Konum Skoru Hesapla' aracını çalıştırın.
"""

import sys
from pathlib import Path
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingParameterFile,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFileDestination,
)


class PropScoreProcessingAlgorithm(QgsProcessingAlgorithm):
    SHP_DIR = "SHP_DIR"
    REGION = "REGION"
    OUTPUT_GPKG = "OUTPUT_GPKG"

    REGION_KEYS = ["nilufer_fsm", "nilufer_ozluce", "nilufer_gorukle", "nilufer_full"]

    def tr(self, string):
        return QCoreApplication.translate("Processing", string)

    def createInstance(self):
        return PropScoreProcessingAlgorithm()

    def name(self):
        return "propscore_building_accessibility"

    def displayName(self):
        return self.tr("Bina Bazlı Emlak Konum Skoru Hesapla (PropScore)")

    def group(self):
        return self.tr("PropScore Location Intelligence")

    def groupId(self):
        return "propscore"

    def shortHelpString(self):
        return self.tr(
            "Geofabrik OSM Shapefile verilerini kullanarak yürünebilir sokak ağı (Dijkstra) "
            "üzerinden binaların Toplu Taşıma, Market, Kafe/Sosyal, Sağlık/Eğitim ve Yeşil Alan "
            "erişilebilirlik skorlarını (0-100) hesaplar ve GeoPackage + Web Haritası üretir."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFile(
                self.SHP_DIR,
                self.tr("Geofabrik Türkiye SHP Klasörü (Boş bırakılırsa Nilüfer Demo çalışır)"),
                behavior=QgsProcessingParameterFile.Folder,
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.REGION,
                self.tr("Pilot Bölge Seçimi"),
                options=self.REGION_KEYS,
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT_GPKG,
                self.tr("Çıktı GeoPackage (.gpkg)"),
                fileFilter="GeoPackage (*.gpkg)",
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        project_root = Path(__file__).resolve().parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.config import REGIONS
        from src.data_loader import generate_nilufer_demo_data, load_geofabrik_bbox
        from src.network_engine import compute_network_accessibility
        from src.scorer import compute_propscores
        from src.exporter import export_qgis_geopackage

        shp_dir = self.parameterAsString(parameters, self.SHP_DIR, context)
        region_idx = self.parameterAsEnum(parameters, self.REGION, context)
        out_gpkg = self.parameterAsFileOutput(parameters, self.OUTPUT_GPKG, context)

        region_key = self.REGION_KEYS[region_idx]
        bbox = REGIONS[region_key]["bbox"]

        feedback.pushInfo(f"Bölge: {REGIONS[region_key]['name']} | BBOX: {bbox}")

        if shp_dir and Path(shp_dir).exists():
            buildings, roads, pois = load_geofabrik_bbox(shp_dir, bbox=bbox)
        else:
            feedback.pushInfo("SHP klasörü verilmedi, Bursa Nilüfer demo verisi üretiliyor...")
            buildings, roads, pois = generate_nilufer_demo_data(bbox=bbox)

        feedback.setProgress(35)
        bldg_access = compute_network_accessibility(buildings, roads, pois)

        feedback.setProgress(75)
        bldg_scored = compute_propscores(bldg_access)

        gpkg_path = export_qgis_geopackage(bldg_scored, roads, pois, output_gpkg=out_gpkg)
        feedback.setProgress(100)
        feedback.pushInfo(f"Tamamlandı: {gpkg_path}")

        return {self.OUTPUT_GPKG: str(gpkg_path)}
