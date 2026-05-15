import os
import glob
import re
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
# 1. DIRECTORY SETUP
# ─────────────────────────────────────────────
def setup_dirs():
    for d in ['data/raw', 'data/processed', 'data/spatial', 'scripts', 'results']:
        os.makedirs(d, exist_ok=True)

# ─────────────────────────────────────────────
# 2. MERGE ACADEMY DATA
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
            district = re.search(r'_([\w]+)\.xlsx$', f)
            df['지역'] = district.group(1) if district else f
            all_dfs.append(df)
        except Exception as e:
            print(f"  Error reading {f}: {e}")
    merged = pd.concat(all_dfs, ignore_index=True)
    merged.to_csv("data/processed/academies_merged.csv", index=False, encoding='utf-8-sig')
    print(f"  Merged {len(merged):,} academies from {len(files)} districts.")
    return merged

# ─────────────────────────────────────────────
# 3. SIMULATION: Incheon-wide academy distribution
# ─────────────────────────────────────────────
def generate_simulation_points(df_academies):
    """
    Generate realistic simulated coordinates based on actual district academy counts.
    Proportional allocation across 8 Incheon districts.
    """
    print("[Step 2] Generating simulation coordinates for all Incheon districts...")

    # Real district centroids in Incheon (lat, lon, std_lat, std_lon, weight)
    districts = {
        '부평구':  (37.508, 126.722, 0.020, 0.018),
        '남동구':  (37.449, 126.731, 0.018, 0.018),
        '연수구':  (37.400, 126.652, 0.018, 0.020),
        '서구':    (37.547, 126.676, 0.022, 0.018),
        '계양구':  (37.537, 126.739, 0.018, 0.016),
        '미추홀구':(37.460, 126.650, 0.016, 0.015),
        '중구':    (37.475, 126.614, 0.014, 0.012),
        '동구':    (37.476, 126.644, 0.012, 0.010),
    }

    # Count actual academies per district for proportional weighting
    district_counts = {}
    for district_name in districts:
        count = len(df_academies[df_academies['지역'].str.contains(district_name, na=False)])
        district_counts[district_name] = max(count, 1)

    total = sum(district_counts.values())
    total_points = 400  # total simulation points across Incheon

    all_lats, all_lons, all_districts = [], [], []
    for name, (lat, lon, slat, slon) in districts.items():
        n = max(int(total_points * district_counts[name] / total), 5)
        all_lats.extend(np.random.normal(lat, slat, n))
        all_lons.extend(np.random.normal(lon, slon, n))
        all_districts.extend([name] * n)

    df_points = pd.DataFrame({'lat': all_lats, 'lon': all_lons, '지역': all_districts})
    
    # Save cache
    df_points.to_csv("data/processed/geocoded_cache.csv", index=False, encoding='utf-8-sig')
    print(f"  Generated {len(df_points)} simulation points across {len(districts)} districts.")
    return df_points

# ─────────────────────────────────────────────
# 4. VORONOI WITH DENSITY COLORING
# ─────────────────────────────────────────────
def compute_density_color(region_vertices, all_points):
    """Estimate local density by counting points within the bounding box of the polygon."""
    if len(region_vertices) == 0:
        return 0
    poly_lats = [v[1] for v in region_vertices]
    poly_lons = [v[0] for v in region_vertices]
    lat_min, lat_max = min(poly_lats), max(poly_lats)
    lon_min, lon_max = min(poly_lons), max(poly_lons)
    mask = (
        (all_points[:, 1] >= lat_min) & (all_points[:, 1] <= lat_max) &
        (all_points[:, 0] >= lon_min) & (all_points[:, 0] <= lon_max)
    )
    return mask.sum()

def density_to_color(density, max_density):
    """Map density to a color: low=cool blue, medium=yellow, high=hot red."""
    if max_density == 0:
        return '#4a90d9'
    ratio = min(density / max_density, 1.0)
    # Color stops: 0=blue, 0.5=yellow-green, 1=red
    if ratio < 0.33:
        t = ratio / 0.33
        r = int(67 + t * (144 - 67))
        g = int(133 + t * (238 - 133))
        b = int(196 + t * (99 - 196))
    elif ratio < 0.66:
        t = (ratio - 0.33) / 0.33
        r = int(144 + t * (255 - 144))
        g = int(238 + t * (165 - 238))
        b = int(99 + t * (0 - 99))
    else:
        t = (ratio - 0.66) / 0.34
        r = int(255 + t * (220 - 255))
        g = int(165 + t * (38 - 165))
        b = 0
    return f'#{r:02x}{g:02x}{b:02x}'

# ─────────────────────────────────────────────
# 5. BUILD MAP
# ─────────────────────────────────────────────
def build_map(geocoded, df_academies):
    print("[Step 3] Building map...")

    points = np.array(list(zip(geocoded['lon'], geocoded['lat'])))

    # Bounding box expansion for closed Voronoi
    lat_min, lat_max = points[:, 1].min() - 0.05, points[:, 1].max() + 0.05
    lon_min, lon_max = points[:, 0].min() - 0.05, points[:, 0].max() + 0.05
    boundary = np.array([
        [lon_min, lat_min], [lon_min, lat_max], [lon_max, lat_min], [lon_max, lat_max],
        [(lon_min+lon_max)/2, lat_min], [(lon_min+lon_max)/2, lat_max],
        [lon_min, (lat_min+lat_max)/2], [lon_max, (lat_min+lat_max)/2],
    ])
    vor = Voronoi(np.vstack([points, boundary]))

    # Pre-compute densities for coloring
    densities = []
    valid_polys = []
    for region_index in vor.point_region[:len(points)]:
        region = vor.regions[region_index]
        if -1 not in region and len(region) > 0:
            verts = [vor.vertices[i] for i in region]
            d = compute_density_color(verts, points)
            densities.append(d)
            valid_polys.append(verts)
    max_density = max(densities) if densities else 1

    # ── BASE MAP ──────────────────────────────
    center = [points[:, 1].mean(), points[:, 0].mean()]
    m = folium.Map(
        location=center,
        zoom_start=12,
        tiles='CartoDB positron',
        prefer_canvas=True,
    )

    # ── VORONOI LAYER ─────────────────────────
    voronoi_layer = folium.FeatureGroup(name="학원 영역권 (보로노이)", show=True)
    for verts, density in zip(valid_polys, densities):
        color = density_to_color(density, max_density)
        folium.Polygon(
            locations=[[v[1], v[0]] for v in verts],
            color='#555555',
            weight=0.4,
            fill=True,
            fill_color=color,
            fill_opacity=0.45,
        ).add_to(voronoi_layer)
    voronoi_layer.add_to(m)

    # ── HEATMAP LAYER ─────────────────────────
    heat_layer = folium.FeatureGroup(name="학원 밀집도 (열지도)", show=False)
    HeatMap(
        [[row['lat'], row['lon']] for _, row in geocoded.iterrows()],
        radius=25, blur=20, max_zoom=13, min_opacity=0.3
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
        print(f"  Note: Shelter data not loaded ({e})")
    shelter_layer.add_to(m)

    # ── LAYER CONTROL ─────────────────────────
    LayerControl(collapsed=False).add_to(m)

    # ── TITLE & INFO PANEL (HTML overlay) ─────
    district_count = len(df_academies['지역'].unique()) if df_academies is not None else '?'
    total_academies = f"{len(df_academies):,}" if df_academies is not None else '?'

    title_html = f"""
    <div style="
        position: fixed;
        top: 15px; left: 60px;
        z-index: 1000;
        background: rgba(255,255,255,0.95);
        border-radius: 12px;
        padding: 16px 22px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif;
        max-width: 280px;
        border-left: 5px solid #e74c3c;
    ">
        <div style="font-size:16px; font-weight:700; color:#2c3e50; margin-bottom:4px;">
            인천 청소년 쉼터 최적 입지 분석
        </div>
        <div style="font-size:11px; color:#7f8c8d; margin-bottom:12px;">
            Incheon Youth Shelter Location Optimization
        </div>
        <div style="display:flex; gap:16px;">
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:800; color:#e74c3c;">{total_academies}</div>
                <div style="font-size:10px; color:#555;">등록 학원 수</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:800; color:#3498db;">{shelter_count}</div>
                <div style="font-size:10px; color:#555;">인천 쉼터 수</div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:800; color:#27ae60;">{district_count}</div>
                <div style="font-size:10px; color:#555;">분석 지역(구)</div>
            </div>
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # ── LEGEND ────────────────────────────────
    legend_html = """
    <div style="
        position: fixed;
        bottom: 30px; right: 15px;
        z-index: 1000;
        background: rgba(255,255,255,0.95);
        border-radius: 12px;
        padding: 14px 18px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif;
        font-size: 12px;
        min-width: 160px;
    ">
        <div style="font-weight:700; margin-bottom:10px; color:#2c3e50;">학원 밀집도</div>
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
            <div style="width:40px; height:14px; background:linear-gradient(to right, #43c5c3, #90ee63, #ffa500, #dc2626); border-radius:3px;"></div>
            <span style="color:#555;">낮음 → 높음</span>
        </div>
        <hr style="border:none; border-top:1px solid #eee; margin:10px 0;">
        <div style="font-weight:700; margin-bottom:8px; color:#2c3e50;">범례</div>
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:5px;">
            <div style="width:14px; height:14px; border-radius:50%; background:#e74c3c; flex-shrink:0;"></div>
            <span style="color:#555;">청소년 쉼터 (현황)</span>
        </div>
        <div style="display:flex; align-items:center; gap:8px;">
            <div style="width:14px; height:14px; border-radius:2px; background:rgba(67,133,196,0.5); border:1px solid #555; flex-shrink:0;"></div>
            <span style="color:#555;">학원 영역권 (보로노이)</span>
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    output = "results/final_analysis.html"
    m.save(output)
    print(f"\n  Map saved -> {output}")
    print(f"  Total points plotted: {len(points)}")
    print(f"  Voronoi polygons: {len(valid_polys)}")
    print(f"  Shelters marked: {shelter_count}")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    setup_dirs()
    df = merge_academies()

    cache_path = "data/processed/geocoded_cache.csv"
    if os.path.exists(cache_path):
        geocoded = pd.read_csv(cache_path)
        # Regenerate if cache looks wrong (all in same area or too few)
        lat_range = geocoded['lat'].max() - geocoded['lat'].min()
        if len(geocoded) < 50 or lat_range < 0.05:
            print("  Cache outdated or too small, regenerating...")
            os.remove(cache_path)
            geocoded = generate_simulation_points(df)
        else:
            print(f"  Loaded {len(geocoded)} points from cache.")
    else:
        geocoded = generate_simulation_points(df)

    build_map(geocoded, df)
    print("\nDONE! Open results/final_analysis.html to view the map.")
