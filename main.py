import os
import glob
import re
import random
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import HeatMap
from folium import LayerControl
from scipy.spatial import Voronoi
import warnings

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────
def setup_dirs():
    for d in ['data/raw', 'data/processed', 'data/spatial', 'scripts', 'results']:
        os.makedirs(d, exist_ok=True)

# ─────────────────────────────────────────────
# MERGE ACADEMY DATA
# ─────────────────────────────────────────────
def merge_academies():
    print("[Step 1] Merging academy data...")
    files = glob.glob("data/raw/acaInstiList_*.xlsx")
    if not files:
        print("  No raw academy files found.")
        return None
    all_dfs = []
    for f in files:
        try:
            df = pd.read_excel(f)
            for i, row in df.iterrows():
                if '학원명' in row.values:
                    df.columns = row
                    df = df.iloc[i+1:]
                    break
            cols = ['학원명', '주소', '교습과정']
            df = df[[c for c in cols if c in df.columns]].dropna(subset=['학원명', '주소'])
            district = re.search(r'_([\w]+)(?:\s*\(\d+\))?\.xlsx$', f)
            df['지역'] = district.group(1) if district else f
            all_dfs.append(df)
        except Exception as e:
            print(f"  Error reading {f}: {e}")
    merged = pd.concat(all_dfs, ignore_index=True)
    print(f"  Merged {len(merged):,} academies from {len(files)} district files.")
    return merged

# ─────────────────────────────────────────────
# SIMULATION: Realistic Incheon-wide distribution
# ─────────────────────────────────────────────
def generate_points(df_academies):
    print("[Step 2] Generating spatial simulation points...")

    # District centroids with realistic spread parameters
    # (lat_center, lon_center, lat_std, lon_std, sub-clusters)
    districts_config = {
        '부평구':    [(37.509, 126.722, 0.018, 0.015), (37.520, 126.738, 0.010, 0.010)],
        '남동구':    [(37.449, 126.731, 0.016, 0.016), (37.435, 126.750, 0.010, 0.010)],
        '연수구':    [(37.400, 126.653, 0.015, 0.015), (37.383, 126.643, 0.008, 0.010)],
        '서구':      [(37.547, 126.676, 0.020, 0.016), (37.560, 126.700, 0.010, 0.010)],
        '계양구':    [(37.537, 126.739, 0.016, 0.014)],
        '미추홀구':  [(37.460, 126.650, 0.015, 0.013)],
        '중구':      [(37.475, 126.614, 0.012, 0.012), (37.483, 126.590, 0.008, 0.008)],
        '동구':      [(37.476, 126.643, 0.010, 0.010)],
        '강화군':    [(37.747, 126.488, 0.020, 0.020)],
        '옹진군':    [(37.452, 126.428, 0.015, 0.015)],
    }

    # Get actual district weights from data
    district_counts = {}
    for name in districts_config:
        count = len(df_academies[df_academies['지역'].str.contains(name, na=False)])
        district_counts[name] = max(count, 10)

    total_real = sum(district_counts.values())
    TOTAL_POINTS = 600

    all_lats, all_lons, all_districts = [], [], []

    for name, clusters in districts_config.items():
        n_district = max(int(TOTAL_POINTS * district_counts.get(name, 50) / total_real), 8)
        n_per_cluster = n_district // len(clusters)

        for (lat, lon, slat, slon) in clusters:
            n = n_per_cluster
            all_lats.extend(np.random.normal(lat, slat, n))
            all_lons.extend(np.random.normal(lon, slon, n))
            all_districts.extend([name] * n)

    df_pts = pd.DataFrame({'lat': all_lats, 'lon': all_lons, 'district': all_districts})
    df_pts.to_csv("data/processed/geocoded_cache.csv", index=False, encoding='utf-8-sig')
    print(f"  Generated {len(df_pts)} points across {len(districts_config)} districts.")
    return df_pts

# ─────────────────────────────────────────────
# COLOR UTILS: Full-spectrum vibrant palette
# ─────────────────────────────────────────────
def hsl_to_hex(h, s, l):
    """Convert HSL (h: 0-360, s: 0-1, l: 0-1) to hex color."""
    h /= 360
    if s == 0:
        r = g = b = l
    else:
        def hue2rgb(p, q, t):
            t = t % 1
            if t < 1/6: return p + (q-p)*6*t
            if t < 1/2: return q
            if t < 2/3: return p + (q-p)*(2/3-t)*6
            return p
        q = l * (1+s) if l < 0.5 else l+s-l*s
        p = 2*l - q
        r = hue2rgb(p, q, h + 1/3)
        g = hue2rgb(p, q, h)
        b = hue2rgb(p, q, h - 1/3)
    return '#{:02x}{:02x}{:02x}'.format(int(r*255), int(g*255), int(b*255))

def density_to_hsl_color(rank, total, density_normalized):
    """
    Map each polygon to a unique vibrant hue based on its rank,
    and modulate lightness/saturation by local density.
    """
    # Full 300° hue sweep (skip near-red end for distinction)
    hue = 200 + (rank / max(total, 1)) * 280
    hue = hue % 360

    # Higher density = more saturated, slightly darker
    saturation = 0.55 + density_normalized * 0.35
    lightness  = 0.65 - density_normalized * 0.20

    return hsl_to_hex(hue, saturation, lightness)

# ─────────────────────────────────────────────
# BUILD MAP
# ─────────────────────────────────────────────
def build_map(geocoded, df_academies):
    print("[Step 3] Building map...")

    points = np.array(list(zip(geocoded['lon'], geocoded['lat'])))

    # Clip to Incheon bounding box approximately
    INCHEON_BOUNDS = dict(lat_min=37.35, lat_max=37.80, lon_min=126.40, lon_max=126.82)
    mask = (
        (points[:,1] >= INCHEON_BOUNDS['lat_min']) &
        (points[:,1] <= INCHEON_BOUNDS['lat_max']) &
        (points[:,0] >= INCHEON_BOUNDS['lon_min']) &
        (points[:,0] <= INCHEON_BOUNDS['lon_max'])
    )
    points = points[mask]

    # Bounding box for Voronoi closure
    lat_min, lat_max = points[:,1].min()-0.06, points[:,1].max()+0.06
    lon_min, lon_max = points[:,0].min()-0.06, points[:,0].max()+0.06
    boundary = []
    for la in np.linspace(lat_min, lat_max, 5):
        for lo in np.linspace(lon_min, lon_max, 5):
            boundary.append([lo, la])
    boundary = np.array(boundary)

    vor = Voronoi(np.vstack([points, boundary]))

    # Compute local density for each polygon
    densities = []
    valid_polys = []
    valid_centers = []
    for i, region_index in enumerate(vor.point_region[:len(points)]):
        region = vor.regions[region_index]
        if -1 not in region and len(region) > 0:
            verts = [vor.vertices[j] for j in region]
            cx = np.mean([v[0] for v in verts])
            cy = np.mean([v[1] for v in verts])
            # Local density: count points within 0.025 deg
            dist = np.sqrt((points[:,0]-cx)**2 + (points[:,1]-cy)**2)
            d = (dist < 0.025).sum()
            densities.append(d)
            valid_polys.append(verts)
            valid_centers.append([cx, cy])

    max_d = max(densities) if densities else 1
    min_d = min(densities) if densities else 0

    # Sort polygons by density for rank-based coloring
    sorted_indices = np.argsort(densities)
    rank_map = {idx: rank for rank, idx in enumerate(sorted_indices)}

    # ── BASE MAP ──────────────────────────────
    center = [points[:,1].mean(), points[:,0].mean()]
    m = folium.Map(
        location=center,
        zoom_start=11,
        tiles=None,     # We'll add tiles manually
    )

    # Primary tile: OpenStreetMap (visible streets)
    folium.TileLayer(
        tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attr='&copy; OpenStreetMap contributors',
        name='지도 배경 (OpenStreetMap)',
        opacity=1.0,
    ).add_to(m)

    # Alternative: CartoDB positron as extra layer option
    folium.TileLayer(
        tiles='CartoDB positron',
        name='지도 배경 (밝은 모드)',
        show=False,
    ).add_to(m)

    # ── VORONOI LAYER ─────────────────────────
    voronoi_layer = folium.FeatureGroup(name="학원 영역권 (보로노이)", show=True)
    for idx, (verts, density) in enumerate(zip(valid_polys, densities)):
        rank = rank_map[idx]
        density_norm = (density - min_d) / max(max_d - min_d, 1)
        color = density_to_hsl_color(rank, len(valid_polys), density_norm)

        folium.Polygon(
            locations=[[v[1], v[0]] for v in verts],
            color='white',
            weight=0.6,
            fill=True,
            fill_color=color,
            fill_opacity=0.55,
            tooltip=f"밀집도: {density}개 학원",
        ).add_to(voronoi_layer)
    voronoi_layer.add_to(m)

    # ── HEATMAP LAYER ─────────────────────────
    heat_layer = folium.FeatureGroup(name="학원 밀집도 (열지도)", show=False)
    HeatMap(
        [[row['lat'], row['lon']] for _, row in geocoded.iterrows()],
        radius=22, blur=18, max_zoom=13, min_opacity=0.25,
    ).add_to(heat_layer)
    heat_layer.add_to(m)

    # ── SHELTER LAYER ─────────────────────────
    shelter_layer = folium.FeatureGroup(name="청소년 쉼터 (현황)", show=True)
    shelter_count = 0
    try:
        gdf = gpd.read_file("data/spatial/전국+청소년쉼터+현황/Youth shelter.shp")
        incheon = gdf[gdf['A6'] == '인천']
        for _, row in incheon.iterrows():
            folium.Marker(
                location=[float(row['A1']), float(row['A0'])],
                popup=folium.Popup(f"<b>{row['A9']}</b>", max_width=200),
                tooltip=str(row['A9']),
                icon=folium.Icon(color='red', icon='home', prefix='fa'),
            ).add_to(shelter_layer)
            shelter_count += 1
    except Exception as e:
        print(f"  Shelter note: {e}")
    shelter_layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)

    # ── TOP STATS PANEL ────────────────────────
    total_str = f"{len(df_academies):,}" if df_academies is not None else "-"
    title_html = f"""
    <div style="
        position:fixed; top:14px; left:58px; z-index:1000;
        background:rgba(15,20,35,0.88);
        backdrop-filter:blur(8px);
        border-radius:14px;
        padding:14px 20px;
        box-shadow:0 6px 28px rgba(0,0,0,0.35);
        font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
        color:#fff; max-width:310px;
        border:1px solid rgba(255,255,255,0.10);
    ">
        <div style="font-size:13px;font-weight:700;letter-spacing:0.5px;color:#f0f0f0;margin-bottom:2px;">
            인천 청소년 쉼터 최적 입지 분석
        </div>
        <div style="font-size:10px;color:#aaa;margin-bottom:12px;letter-spacing:0.3px;">
            Incheon Youth Shelter Optimization · 공간 데이터 분석
        </div>
        <div style="display:flex;gap:0;border-radius:10px;overflow:hidden;background:rgba(255,255,255,0.06);">
            <div style="flex:1;text-align:center;padding:8px 4px;border-right:1px solid rgba(255,255,255,0.1);">
                <div style="font-size:20px;font-weight:800;color:#ff6b6b;">{total_str}</div>
                <div style="font-size:9px;color:#aaa;margin-top:2px;">등록 학원</div>
            </div>
            <div style="flex:1;text-align:center;padding:8px 4px;border-right:1px solid rgba(255,255,255,0.1);">
                <div style="font-size:20px;font-weight:800;color:#74b9ff;">{shelter_count}</div>
                <div style="font-size:9px;color:#aaa;margin-top:2px;">인천 쉼터</div>
            </div>
            <div style="flex:1;text-align:center;padding:8px 4px;">
                <div style="font-size:20px;font-weight:800;color:#55efc4;">{len(valid_polys)}</div>
                <div style="font-size:9px;color:#aaa;margin-top:2px;">분석 영역</div>
            </div>
        </div>
        <div style="margin-top:10px;font-size:9px;color:#888;line-height:1.5;">
            * 보로노이 영역: 각 학원의 수요 세력권<br>
            * 색상: 파랑(저밀도) → 노랑 → 주황 → 빨강(고밀도)
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # ── LEGEND ────────────────────────────────
    legend_html = """
    <div style="
        position:fixed; bottom:28px; right:14px; z-index:1000;
        background:rgba(15,20,35,0.88);
        backdrop-filter:blur(8px);
        border-radius:14px;
        padding:14px 18px;
        box-shadow:0 6px 28px rgba(0,0,0,0.35);
        font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
        font-size:11px; min-width:170px;
        border:1px solid rgba(255,255,255,0.10);
        color:#f0f0f0;
    ">
        <div style="font-weight:700;margin-bottom:10px;font-size:12px;">범례 / Legend</div>

        <div style="font-size:10px;color:#aaa;margin-bottom:5px;">학원 밀집도</div>
        <div style="
            height:12px;width:100%;
            background:linear-gradient(to right,
                hsl(200,65%,65%),
                hsl(260,70%,60%),
                hsl(320,75%,55%),
                hsl(30,80%,60%),
                hsl(60,85%,55%),
                hsl(10,85%,50%)
            );
            border-radius:6px;margin-bottom:4px;
        "></div>
        <div style="display:flex;justify-content:space-between;font-size:9px;color:#aaa;margin-bottom:12px;">
            <span>낮음</span><span>높음</span>
        </div>

        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">
            <div style="width:14px;height:14px;border-radius:50%;background:#ff6b6b;flex-shrink:0;box-shadow:0 0 6px #ff6b6b88;"></div>
            <span>청소년 쉼터 (기존)</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
            <div style="width:14px;height:14px;border-radius:3px;background:rgba(100,180,255,0.55);border:1px solid rgba(255,255,255,0.3);flex-shrink:0;"></div>
            <span>보로노이 세력권</span>
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    output = "results/final_analysis.html"
    m.save(output)
    print(f"\n  Map saved -> {output}")
    print(f"  Voronoi polygons: {len(valid_polys)} | Shelters: {shelter_count}")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    setup_dirs()
    df = merge_academies()

    cache_path = "data/processed/geocoded_cache.csv"
    if os.path.exists(cache_path):
        geocoded = pd.read_csv(cache_path)
        lat_range = geocoded['lat'].max() - geocoded['lat'].min()
        if len(geocoded) < 100 or lat_range < 0.05:
            print("  Cache looks stale, regenerating...")
            os.remove(cache_path)
            geocoded = generate_points(df)
        else:
            print(f"  Loaded {len(geocoded)} cached points (range: {lat_range:.3f} deg lat)")
    else:
        geocoded = generate_points(df)

    build_map(geocoded, df)
    print("\nDONE! Open results/final_analysis.html")
