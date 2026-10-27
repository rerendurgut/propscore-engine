"""Topological street-network graph builder, multi-source Dijkstra, bus line matcher, and isochrone generator."""

from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString, MultiPoint

from src.config import (
    CATEGORIES,
    METRIC_CRS,
    WALKING_SPEED_M_PER_MIN,
    WGS84_CRS,
)


def _iter_linestrings(geom):
    if geom is None or geom.is_empty:
        return
    if isinstance(geom, LineString):
        yield geom
    elif isinstance(geom, MultiLineString):
        for part in geom.geoms:
            if not part.is_empty:
                yield part


def _densify_coords(coords: List[Tuple[float, float]], max_seg_len: float = 35.0) -> List[Tuple[float, float]]:
    out = [coords[0]]
    for i in range(len(coords) - 1):
        x0, y0 = coords[i]
        x1, y1 = coords[i + 1]
        dx, dy = x1 - x0, y1 - y0
        seg_len = float(np.hypot(dx, dy))
        if seg_len > max_seg_len:
            n_sub = int(np.ceil(seg_len / max_seg_len))
            for k in range(1, n_sub):
                t = k / n_sub
                out.append((x0 + t * dx, y0 + t * dy))
        out.append((x1, y1))
    return out


def build_pedestrian_graph(roads_wgs84: gpd.GeoDataFrame) -> Tuple[nx.Graph, np.ndarray, List[Tuple[float, float]]]:
    """Build a metric pedestrian street graph from road geometries."""
    roads_metric = roads_wgs84.to_crs(METRIC_CRS)
    G = nx.Graph()

    for geom in roads_metric.geometry:
        for line in _iter_linestrings(geom):
            raw_coords = list(line.coords)
            if len(raw_coords) < 2:
                continue
            dense_coords = _densify_coords([(c[0], c[1]) for c in raw_coords], max_seg_len=35.0)
            snapped_nodes = [(round(x * 2.0) / 2.0, round(y * 2.0) / 2.0) for x, y in dense_coords]
            for u, v in zip(snapped_nodes[:-1], snapped_nodes[1:]):
                if u == v:
                    continue
                dist = float(np.hypot(v[0] - u[0], v[1] - u[1]))
                if G.has_edge(u, v):
                    if dist < G[u][v]["weight"]:
                        G[u][v]["weight"] = dist
                else:
                    G.add_edge(u, v, weight=dist)

    if G.number_of_nodes() == 0:
        raise ValueError("Yol ağından geçerli hiçbir düğüm (node) oluşturulamadı.")

    node_keys = list(G.nodes())
    node_coords = np.array(node_keys, dtype=np.float64)
    print(
        f"✓ Yaya yol ağı grafı kuruldu: {G.number_of_nodes():,} düğüm | "
        f"{G.number_of_edges():,} sokak bağlantısı"
    )
    return G, node_coords, node_keys


def compute_network_accessibility(
    buildings_wgs84: gpd.GeoDataFrame,
    roads_wgs84: gpd.GeoDataFrame,
    pois_wgs84: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Calculate real street-network walking distances, times, bus routes, nearby markets,
    and nearest POI coordinates from every building using multi-source Dijkstra.
    """
    G, node_coords, node_keys = build_pedestrian_graph(roads_wgs84)
    tree = cKDTree(node_coords)

    bldg_metric = buildings_wgs84.to_crs(METRIC_CRS)
    bldg_centroids_metric = bldg_metric.geometry.centroid
    bldg_xy = np.column_stack([bldg_centroids_metric.x.values, bldg_centroids_metric.y.values])

    bldg_centroids_wgs = gpd.GeoSeries(bldg_centroids_metric, crs=METRIC_CRS).to_crs(WGS84_CRS)

    result = buildings_wgs84.copy()
    result["area_m2"] = np.round(bldg_metric.geometry.area.values, 0).astype(int)
    result["lat"] = np.round(bldg_centroids_wgs.y.values, 5)
    result["lon"] = np.round(bldg_centroids_wgs.x.values, 5)

    # Nearest named street
    named_roads = roads_wgs84[roads_wgs84["name"].notnull() & (roads_wgs84["name"].str.strip() != "")].copy()
    if len(named_roads) > 0:
        nr_metric = named_roads.to_crs(METRIC_CRS)
        nr_pts = nr_metric.geometry.centroid
        nr_xy = np.column_stack([nr_pts.x.values, nr_pts.y.values])
        _, nr_idxs = cKDTree(nr_xy).query(bldg_xy, k=1)
        nr_names = named_roads["name"].values
        result["street_name"] = [str(nr_names[i]) for i in nr_idxs]
    else:
        result["street_name"] = "Sokak"

    bldg_snap_dists, bldg_node_idxs = tree.query(bldg_xy, k=1)
    bldg_nodes = [node_keys[idx] for idx in bldg_node_idxs]

    pois_wgs = pois_wgs84.to_crs(WGS84_CRS).copy()
    pois_metric = pois_wgs.to_crs(METRIC_CRS).copy()
    if "extra_info" not in pois_metric.columns:
        pois_metric["extra_info"] = ""

    if len(pois_metric) > 0:
        poi_pts = pois_metric.geometry.centroid
        poi_xy = np.column_stack([poi_pts.x.values, poi_pts.y.values])
        poi_snap_dists, poi_node_idxs = tree.query(poi_xy, k=1)
        pois_metric["node_key"] = [node_keys[idx] for idx in poi_node_idxs]
        pois_metric["snap_dist_m"] = poi_snap_dists
        pois_metric["poi_lat"] = np.round(pois_wgs.geometry.y.values, 5)
        pois_metric["poi_lon"] = np.round(pois_wgs.geometry.x.values, 5)
    else:
        pois_metric["node_key"] = []
        pois_metric["snap_dist_m"] = []
        pois_metric["poi_lat"] = []
        pois_metric["poi_lon"] = []

    for cat_key, cfg in CATEGORIES.items():
        cat_pois = pois_metric[pois_metric["category"] == cat_key]
        dist_col = f"{cat_key}_dist_m"
        mins_col = f"{cat_key}_walk_min"
        name_col = f"{cat_key}_nearest_name"
        lat_col = f"{cat_key}_poi_lat"
        lon_col = f"{cat_key}_poi_lon"
        extra_col = f"{cat_key}_extra"

        if len(cat_pois) == 0:
            result[dist_col] = 9999.0
            result[mins_col] = 99.9
            result[name_col] = "Bulunamadı"
            result[lat_col] = result["lat"]
            result[lon_col] = result["lon"]
            result[extra_col] = ""
            continue

        source_nodes = list(cat_pois["node_key"].unique())
        node_to_poi_info: Dict[Tuple[float, float], Tuple[str, float, float, str]] = {}
        for _, row in cat_pois.iterrows():
            nk = row["node_key"]
            raw_name = row.get("name")
            fclass_label = str(row.get("fclass", cat_key)).replace("_", " ").title()
            display_name = str(raw_name).strip() if pd.notnull(raw_name) and str(raw_name).strip() else fclass_label
            extra_val = str(row.get("extra_info") or "").strip()
            if nk not in node_to_poi_info or (extra_val and not node_to_poi_info[nk][3]):
                node_to_poi_info[nk] = (display_name, float(row["poi_lat"]), float(row["poi_lon"]), extra_val)

        lengths, paths = nx.multi_source_dijkstra(G, sources=source_nodes, weight="weight")

        bldg_dists, bldg_mins, bldg_names, bldg_poi_lats, bldg_poi_lons, bldg_extras = [], [], [], [], [], []

        for b_idx, b_node in enumerate(bldg_nodes):
            if b_node in lengths:
                net_dist = float(lengths[b_node]) + float(bldg_snap_dists[b_idx])
                origin_poi_node = paths[b_node][0]
                nearest_label, p_lat, p_lon, ext = node_to_poi_info.get(
                    origin_poi_node,
                    (cfg.label_tr, float(result["lat"].iloc[b_idx]), float(result["lon"].iloc[b_idx]), ""),
                )
            else:
                b_pt = bldg_xy[b_idx]
                cat_xy = np.column_stack([cat_pois.geometry.x.values, cat_pois.geometry.y.values])
                d_euc = np.hypot(cat_xy[:, 0] - b_pt[0], cat_xy[:, 1] - b_pt[1])
                min_i = int(np.argmin(d_euc))
                net_dist = float(d_euc[min_i] * 1.30)
                raw_n = cat_pois.iloc[min_i].get("name")
                fc_lbl = str(cat_pois.iloc[min_i].get("fclass", cat_key)).replace("_", " ").title()
                nearest_label = str(raw_n).strip() if pd.notnull(raw_n) and str(raw_n).strip() else fc_lbl
                p_lat = float(cat_pois.iloc[min_i]["poi_lat"])
                p_lon = float(cat_pois.iloc[min_i]["poi_lon"])
                ext = str(cat_pois.iloc[min_i].get("extra_info") or "").strip()

            walk_min = net_dist / WALKING_SPEED_M_PER_MIN
            bldg_dists.append(round(net_dist, 1))
            bldg_mins.append(round(walk_min, 1))
            bldg_names.append(nearest_label)
            bldg_poi_lats.append(p_lat)
            bldg_poi_lons.append(p_lon)
            bldg_extras.append(ext)

        result[dist_col] = bldg_dists
        result[mins_col] = bldg_mins
        result[name_col] = bldg_names
        result[lat_col] = bldg_poi_lats
        result[lon_col] = bldg_poi_lons
        result[extra_col] = bldg_extras

    # Enrich each building with:
    # 1) All unique bus lines within ~5 min walk (400m radius)
    bus_pois = pois_metric[pois_metric["category"] == "bus"]
    if len(bus_pois) > 0:
        bus_xy = np.column_stack([bus_pois.geometry.x.values, bus_pois.geometry.y.values])
        bus_tree = cKDTree(bus_xy)
        bus_lines_arr = bus_pois["extra_info"].astype(str).values
        nearby_bus_idxs = bus_tree.query_ball_point(bldg_xy, r=360.0)
        all_nearby_lines = []
        for idxs, nearest_ext in zip(nearby_bus_idxs, result["bus_extra"].values):
            line_set = set()
            if nearest_ext:
                for l in str(nearest_ext).split(","):
                    if l.strip():
                        line_set.add(l.strip())
            for i in idxs:
                for l in bus_lines_arr[i].split(","):
                    if l.strip():
                        line_set.add(l.strip())
            sorted_lines = sorted(line_set)
            all_nearby_lines.append(", ".join(sorted_lines[:18]))
        result["bus_lines"] = all_nearby_lines
    else:
        result["bus_lines"] = result.get("bus_extra", "")

    # 2) Top nearby named Markets / Supermarkets / Bakeries / Malls within 15 min walk
    market_pois = pois_metric[pois_metric["category"] == "market"].copy()
    if len(market_pois) > 0:
        m_xy = np.column_stack([market_pois.geometry.x.values, market_pois.geometry.y.values])
        m_tree = cKDTree(m_xy)
        m_names = market_pois["name"].astype(str).values
        k_val = min(6, len(market_pois))
        dists, idxs = m_tree.query(bldg_xy, k=k_val)
        if k_val == 1:
            dists = dists[:, None]
            idxs = idxs[:, None]
        market_summaries = []
        for b_i in range(len(bldg_xy)):
            seen = set()
            items = []
            for d_euc, m_idx in zip(dists[b_i], idxs[b_i]):
                if d_euc > 950.0:
                    continue
                nm = m_names[m_idx].strip()
                if nm.lower() in ("supermarket", "convenience", "bakery", "mall", "grocery store") or nm.lower() in seen:
                    continue
                seen.add(nm.lower())
                est_min = round((float(d_euc) * 1.25) / WALKING_SPEED_M_PER_MIN, 1)
                items.append(f"{nm} ({est_min} dk)")
                if len(items) >= 4:
                    break
            market_summaries.append(" • ".join(items) if items else result["market_nearest_name"].iloc[b_i])
        result["nearby_markets_15m"] = market_summaries
    else:
        result["nearby_markets_15m"] = result.get("market_nearest_name", "")

    # 3) Total amenities within 15 min walk (~880m straight -> ~1125m network)
    if len(pois_metric) > 0:
        all_poi_xy = np.column_stack([pois_metric.geometry.x.values, pois_metric.geometry.y.values])
        poi_tree = cKDTree(all_poi_xy)
        nearby_15m = poi_tree.query_ball_point(bldg_xy, r=850.0)
        result["poi_count_10min"] = [len(lst) for lst in nearby_15m]
    else:
        result["poi_count_10min"] = 0

    return result
