"""PropScore - Hyperlocal Real Estate Accessibility & Location Intelligence Engine."""

import os
from pathlib import Path

__version__ = "0.1.0"

# Auto-configure GDAL_DATA and PROJ_LIB if running via macOS QGIS bundled Python
_qgis_res = Path("/Applications/QGIS.app/Contents/Resources/qgis")
if _qgis_res.exists():
    _gdal_dir = _qgis_res / "gdal"
    _proj_dir = _qgis_res / "proj"
    if _gdal_dir.exists() and "GDAL_DATA" not in os.environ:
        os.environ["GDAL_DATA"] = str(_gdal_dir)
    if _proj_dir.exists():
        if "PROJ_LIB" not in os.environ:
            os.environ["PROJ_LIB"] = str(_proj_dir)
        if "PROJ_DATA" not in os.environ:
            os.environ["PROJ_DATA"] = str(_proj_dir)
