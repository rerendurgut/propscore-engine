# 🏙️ PropScore Engine — Bursa / Nilüfer 9-Kriterli Konum & Isochrone Zekası (WebGL GPU + QGIS)

**PropScore Engine**, Bursa / Nilüfer (**Özlüce, 23 Nisan, Ataevler, FSM Bulvarı, İhsaniye, Beşevler, Konak, Odunluk**) bölgesindeki **20.651 gerçek bina poligonunu** sokak ağı tabanlı (Dijkstra yaya rotalama) erişilebilirlik analizine tabi tutan uçtan uca bir **Coğrafi Bilgi Sistemi (QGIS + WebGL 60 FPS Web GIS)** platformudur.

---

## 🚀 Mimari Öne Çıkanlar

1. **⚡ 60 FPS WebGL 2 GPU Harita Motoru (`MapLibre GL JS`):**
   - Klasik DOM/SVG tabanlı haritaların aksine **20.651 bina poligonu**, **11.612 sokak segmenti**, **BursaRay metro hattı** ve **10.608 hizmet noktası** doğrudan ekran kartı (GPU) üzerinde çizilir.
   - **2B / 3B Bina Görünümü (Extrusion):** Harita katman panelinden tek tıkla 3 boyutlu bina yüksekliği görünümüne geçilebilir.
   - **Sözlük Sıkıştırmalı Parçalı Veri Mimarisi (`docs/data/`):** `docs/index.html` yalnızca **61 KB** boyutundadır; harita altlığı (`basemap.js`), hizmet noktaları (`pois.js`) ve sıkıştırılmış bina verisi (`buildings.js`) parçalı yüklenerek GitHub Pages CDN üzerinden Gzip/Brotli ile **~2 MB** boyutta saniyeler içinde açılır.

2. **🟣 Anlık (< 3 ms) Sokak Ağı Tabanlı 5 / 10 / 15 Dk Yürüme Isochrone & Dinamik POI Filtresi:**
   - İkili Yığın (Binary Min-Heap) Dijkstra + 2B Uzamsal Izgara (Spatial Hash Grid) sayesinde herhangi bir binaya tıklandığında **375m (5 dk)**, **750m (10 dk)** ve **1.125m (15 dk)** yürüme halkaları `< 3 milisaniyede` hesaplanır.
   - Haritada **yalnızca seçili binanın 15 dakikalık yürüme Isochrone alanı içinde kalan POI noktaları** gösterilir ve sağ panelden kategori bazlı (`🏥 Hastane/ASM`, `🎓 Okul/Eğitim`, `🛒 Market/AVM`, `💊 Eczane`, `🏦 Banka/ATM`, `🚌 Durak/Metro` vb.) filtrelenebilir.

3. **📊 9 Bağımsız Değerlendirme Kriteri & Çoklu Seçenek Listesi:**
   - `🚇 BursaRay Metro & Raylı Sistem` (`%16`)
   - `🚌 Otobüs Durağı & Hat Erişimi` (`%12` — Durağın önünden geçen tüm **BURULAŞ** hat numaraları rozet olarak listelenir)
   - `🛒 Market, AVM & Pazar Yeri` (`%18` — Süpermarket, AVM, Semt Pazarı, Fırın, Kasap, Manav)
   - `🏦 Banka, ATM, Posta & Günlük Hizmet` (`%10` — Banka Şubesi, ATM, PTT, Kargo Şubeleri, Noter, Kırtasiye, Kuru Temizleme, Kuaför)
   - `🎓 Okul & Eğitim Kurumları` (`%12` — İlkokul/Ortaokul, Lise, Kolej/Özel Okul, Anaokulu/Kreş, Üniversite, Kütüphane)
   - `🏥 Hastane, ASM, Tıp Merkezi & Klinik` (`%10` — Hastaneler, Aile Sağlığı Merkezleri (ASM), Tıp Merkezleri/Poliklinikler, Diş Klinikleri, Uzman Muayenehaneler)
   - `💊 Eczane & Medikal` (`%8`)
   - `☕ Kafe, Restoran & Sosyal Yaşam` (`%8`)
   - `🌳 Park, Yeşil Alan & Spor` (`%6`)

---

## 📂 Proje Yapısı

```text
├── docs/
│   ├── index.html                  # 61 KB WebGL GPU (MapLibre GL JS) Uygulama Kabuğu
│   └── data/
│       ├── basemap.js              # Vektör Yol, Raylı Sistem, Arazi Kullanımı ve Su Katmanları
│       ├── pois.js                 # 9 Kategoride Doğrulanmış 10.608 Hizmet Noktası
│       └── buildings.js            # Sözlük Sıkıştırmalı 20.651 Bina Poligonu ve Skorları
├── src/
│   ├── config.py                   # 9 Kriter Ağırlıkları, Mesafe Eğrileri ve Bölge BBOX Tanımları
│   ├── data_loader.py              # Overture Maps + CHECKET BURULAŞ/BursaRay + OSM Veri Birleştirici
│   ├── network_engine.py           # Çok Kaynaklı Dijkstra Yaya Ağı Hesaplama Motoru
│   ├── scorer.py                   # 0-100 PropScore ve A+/A/B/C/D Sınıf Hesaplayıcı
│   └── exporter.py                 # QGIS GeoPackage (.gpkg) ve WebGL Web GIS Üretici
├── styles/
│   └── propscore_buildings.qml     # QGIS Otomatik Renklendirme Stil Dosyası
├── qgis_processing_script.py       # QGIS Processing Toolbox Eklenti Betiği
└── run.py                          # Uçtan Uca Analiz ve Harita Üretim Komutu
```

---

## 🛠️ Yerelde Çalıştırma

```bash
/Applications/QGIS.app/Contents/MacOS/python run.py
```
