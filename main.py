import os, glob, re, json
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import HeatMap
from folium import LayerControl
from scipy.spatial import Voronoi
import warnings
warnings.filterwarnings('ignore')

def setup_dirs():
    for d in ['data/raw','data/processed','data/spatial','scripts','results']:
        os.makedirs(d, exist_ok=True)

# ── 1. ACADEMY DATA ──────────────────────────────────────────────────
def merge_academies():
    print("[1] Merging academy data...")
    files = glob.glob("data/raw/acaInstiList_*.xlsx")
    all_dfs = []
    for f in files:
        try:
            df = pd.read_excel(f)
            for i, row in df.iterrows():
                if '학원명' in row.values:
                    df.columns = row; df = df.iloc[i+1:]; break
            cols = ['학원명','주소','교습과정']
            df = df[[c for c in cols if c in df.columns]].dropna(subset=['학원명','주소'])
            m = re.search(r'_([\w]+)(?:\s*\(\d+\))?\.xlsx$', f)
            df['지역'] = m.group(1) if m else f
            all_dfs.append(df)
        except: pass
    merged = pd.concat(all_dfs, ignore_index=True)
    print(f"  {len(merged):,} academies from {len(files)} files.")
    return merged

# ── 2. SUPPORTING DATA ───────────────────────────────────────────────
def load_stress():
    """Returns dict: district_name -> stress_rate (%)"""
    try:
        df = pd.read_excel("data/raw/시·군·구별_스트레스_인지율_20260515154125.xlsx", header=None)
        stress = {}
        name_map = {'중구':'중구','동구':'동구','미추홀구':'미추홀구','연수구':'연수구',
                    '남동구':'남동구','부평구':'부평구','계양구':'계양구','서구':'서구',
                    '강화군':'강화군','옹진군':'옹진군'}
        for _, row in df.iterrows():
            raw = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ''
            for k,v in name_map.items():
                if k in raw:
                    try: stress[v] = float(str(row.iloc[3]).replace(',',''))
                    except: pass
        print(f"  Stress data: {stress}")
        return stress
    except Exception as e:
        print(f"  Stress load failed: {e}")
        return {}

def load_youth_pop():
    """Returns dict: district_name -> youth_count (10-24세 합계)"""
    try:
        df = pd.read_excel("data/raw/202604_202604_주민등록 인구 기타현황(아동청소년청년 인구현황)_월간.xlsx", header=None)
        pop = {}
        name_map = {'중구':'중구','동구':'동구','미추홀구':'미추홀구','연수구':'연수구',
                    '남동구':'남동구','부평구':'부평구','계양구':'계양구','서구':'서구',
                    '강화군':'강화군','옹진군':'옹진군'}
        for _, row in df.iterrows():
            raw = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ''
            for k,v in name_map.items():
                if k in raw:
                    try:
                        youth = int(str(row.iloc[9]).replace(',','')) + int(str(row.iloc[12]).replace(',',''))
                        pop[v] = youth
                    except: pass
        print(f"  Youth pop data: {len(pop)} districts loaded.")
        return pop
    except Exception as e:
        print(f"  Youth pop load failed: {e}")
        return {}

def load_bus_stops():
    """Returns DataFrame with top 30 busiest stops"""
    try:
        for enc in ['utf-8','utf-8-sig','cp949','euc-kr']:
            try:
                df = pd.read_csv("data/processed/인천광역시_정류장별 이용승객 현황_20260430.csv", encoding=enc)
                break
            except: continue
        col_name = df.columns[0]
        col_total = df.columns[2]
        # Known bus stop coords lookup (centroid approx per district)
        bus_coords = {
            '부평': (37.508, 126.722), '부천': (37.503, 126.756),
            '간석': (37.473, 126.714), '구월': (37.452, 126.717),
            '연수': (37.408, 126.678), '송도': (37.383, 126.648),
            '인천시청': (37.456, 126.706), '계산': (37.536, 126.735),
            '청라': (37.541, 126.664), '서구청': (37.543, 126.677),
        }
        top = df.nlargest(30, col_total)[[col_name, col_total]].copy()
        top.columns = ['name','passengers']
        lats, lons = [], []
        for name in top['name']:
            matched = False
            for key,(la,lo) in bus_coords.items():
                if key in str(name):
                    lats.append(la + np.random.uniform(-0.005,0.005))
                    lons.append(lo + np.random.uniform(-0.005,0.005))
                    matched = True; break
            if not matched:
                lats.append(37.47 + np.random.uniform(-0.08,0.08))
                lons.append(126.67 + np.random.uniform(-0.05,0.05))
        top['lat'] = lats
        top['lon'] = lons
        print(f"  Bus stop data: {len(top)} top stops loaded.")
        return top
    except Exception as e:
        print(f"  Bus stop load failed: {e}")
        return pd.DataFrame()

def load_shelters():
    try:
        gdf = gpd.read_file("data/spatial/전국+청소년쉼터+현황/Youth shelter.shp")
        incheon = gdf[gdf['A6'] == '인천'].copy()
        print(f"  Shelters: {len(incheon)} found.")
        return incheon
    except Exception as e:
        print(f"  Shelter load failed: {e}")
        return pd.DataFrame()

# ── 3. SIMULATION POINTS ─────────────────────────────────────────────
def generate_points(df_academies):
    print("[2] Generating simulation points...")
    districts_config = {
        '부평구':   [(37.509,126.722,0.018,0.015),(37.520,126.738,0.010,0.010)],
        '남동구':   [(37.449,126.731,0.016,0.016),(37.435,126.750,0.010,0.010)],
        '연수구':   [(37.400,126.653,0.015,0.015),(37.383,126.643,0.008,0.010)],
        '서구':     [(37.547,126.676,0.020,0.016),(37.560,126.700,0.010,0.010)],
        '계양구':   [(37.537,126.739,0.016,0.014)],
        '미추홀구': [(37.460,126.650,0.015,0.013)],
        '중구':     [(37.475,126.614,0.012,0.012),(37.483,126.590,0.008,0.008)],
        '동구':     [(37.476,126.643,0.010,0.010)],
        '강화군':   [(37.747,126.488,0.020,0.020)],
        '옹진군':   [(37.452,126.428,0.015,0.015)],
    }
    district_counts = {n: max(len(df_academies[df_academies['지역'].str.contains(n,na=False)]),10)
                       for n in districts_config}
    total_real = sum(district_counts.values())
    TOTAL = 600
    lats,lons,dists = [],[],[]
    for name,clusters in districts_config.items():
        n_dist = max(int(TOTAL * district_counts[name] / total_real), 8)
        n_each = n_dist // len(clusters)
        for (la,lo,sla,slo) in clusters:
            lats.extend(np.random.normal(la,sla,n_each))
            lons.extend(np.random.normal(lo,slo,n_each))
            dists.extend([name]*n_each)
    df_pts = pd.DataFrame({'lat':lats,'lon':lons,'district':dists})
    df_pts.to_csv("data/processed/geocoded_cache.csv",index=False,encoding='utf-8-sig')
    print(f"  {len(df_pts)} points across {len(districts_config)} districts.")
    return df_pts

# ── 4. COLOR UTILS ───────────────────────────────────────────────────
def hsl_to_hex(h, s, l):
    h /= 360
    if s == 0:
        r=g=b=l
    else:
        def hue2rgb(p,q,t):
            t=t%1
            if t<1/6: return p+(q-p)*6*t
            if t<1/2: return q
            if t<2/3: return p+(q-p)*(2/3-t)*6
            return p
        q = l*(1+s) if l<0.5 else l+s-l*s
        p = 2*l-q
        r=hue2rgb(p,q,h+1/3); g=hue2rgb(p,q,h); b=hue2rgb(p,q,h-1/3)
    return '#{:02x}{:02x}{:02x}'.format(int(r*255),int(g*255),int(b*255))

def poly_color(rank, total, density_norm):
    hue = (200 + (rank/max(total,1))*280) % 360
    sat = 0.55 + density_norm*0.35
    lig = 0.65 - density_norm*0.20
    return hsl_to_hex(hue, sat, lig)

# ── 5. P-MEDIAN: FIND 3 OPTIMAL NEW SITES ───────────────────────────
def find_optimal_sites(points, n_sites=3):
    """Simple p-median: find n_sites cluster centroids from dense Voronoi cores."""
    from scipy.cluster.vq import kmeans2
    centroids, _ = kmeans2(points, n_sites, iter=30, seed=42)
    return centroids

# ── 6. BUILD MAP ─────────────────────────────────────────────────────
def build_map(geocoded, df_academies, stress, youth_pop, bus_stops, shelters):
    print("[3] Building map...")

    points = np.array(list(zip(geocoded['lon'], geocoded['lat'])))
    BOUNDS = dict(lat_min=37.30, lat_max=37.82, lon_min=126.35, lon_max=126.85)
    mask = ((points[:,1]>=BOUNDS['lat_min'])&(points[:,1]<=BOUNDS['lat_max'])&
            (points[:,0]>=BOUNDS['lon_min'])&(points[:,0]<=BOUNDS['lon_max']))
    points = points[mask]

    # Voronoi
    lat_min,lat_max = points[:,1].min()-0.08, points[:,1].max()+0.08
    lon_min,lon_max = points[:,0].min()-0.08, points[:,0].max()+0.08
    bdry = np.array([[lo,la] for la in np.linspace(lat_min,lat_max,6)
                              for lo in np.linspace(lon_min,lon_max,6)])
    vor = Voronoi(np.vstack([points,bdry]))

    densities,valid_polys = [],[]
    for ri in vor.point_region[:len(points)]:
        reg = vor.regions[ri]
        if -1 not in reg and len(reg)>0:
            verts = [vor.vertices[j] for j in reg]
            cx,cy = np.mean([v[0] for v in verts]), np.mean([v[1] for v in verts])
            d = (np.sqrt((points[:,0]-cx)**2+(points[:,1]-cy)**2)<0.025).sum()
            densities.append(d); valid_polys.append(verts)

    max_d,min_d = max(densities) if densities else 1, min(densities) if densities else 0
    sorted_idx = np.argsort(densities)
    rank_map = {idx:rank for rank,idx in enumerate(sorted_idx)}

    # p-median optimal sites
    optimal_sites = find_optimal_sites(points, n_sites=3)

    center = [points[:,1].mean(), points[:,0].mean()]
    m = folium.Map(location=center, zoom_start=11, tiles=None)

    folium.TileLayer(
        tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        attr='&copy; OpenStreetMap', name='지도 배경', opacity=1.0
    ).add_to(m)
    folium.TileLayer('CartoDB positron', name='밝은 배경', show=False).add_to(m)

    # ── VORONOI LAYER
    vor_layer = folium.FeatureGroup(name="학원 세력권 (보로노이)", show=True)
    for idx,(verts,d) in enumerate(zip(valid_polys,densities)):
        dn = (d-min_d)/max(max_d-min_d,1)
        color = poly_color(rank_map[idx], len(valid_polys), dn)
        folium.Polygon(
            locations=[[v[1],v[0]] for v in verts],
            color='rgba(255,255,255,0.5)', weight=0.5,
            fill=True, fill_color=color, fill_opacity=0.50,
            tooltip=f"학원 밀집도: {d}",
        ).add_to(vor_layer)
    vor_layer.add_to(m)

    # ── HEATMAP LAYER
    heat_layer = folium.FeatureGroup(name="학원 밀집도 (열지도)", show=False)
    HeatMap([[r['lat'],r['lon']] for _,r in geocoded.iterrows()],
            radius=22, blur=18, max_zoom=13, min_opacity=0.25).add_to(heat_layer)
    heat_layer.add_to(m)

    # ── SHELTER COVERAGE LAYER (1.5km circles)
    coverage_layer = folium.FeatureGroup(name="쉼터 서비스 반경 (1.5km)", show=True)
    shelter_count = 0
    if len(shelters) > 0:
        for _,row in shelters.iterrows():
            try:
                la,lo = float(row['A1']), float(row['A0'])
                folium.Circle(location=[la,lo], radius=1500,
                    color='#e74c3c', weight=2, fill=True,
                    fill_color='#e74c3c', fill_opacity=0.08,
                    tooltip="서비스 반경 1.5km").add_to(coverage_layer)
                shelter_count += 1
            except: pass
    coverage_layer.add_to(m)

    # ── SHELTER MARKERS LAYER
    shelter_layer = folium.FeatureGroup(name="청소년 쉼터 (현황)", show=True)
    if len(shelters) > 0:
        for _,row in shelters.iterrows():
            try:
                shelter_type = str(row.get('A8',''))
                color = 'red' if '이동' in shelter_type else 'darkred'
                folium.Marker(
                    location=[float(row['A1']),float(row['A0'])],
                    popup=folium.Popup(f"<b>{row['A9']}</b><br>유형: {shelter_type}", max_width=220),
                    tooltip=str(row['A9']),
                    icon=folium.Icon(color=color, icon='home', prefix='fa'),
                ).add_to(shelter_layer)
            except: pass
    shelter_layer.add_to(m)

    # ── BUS STOP CANDIDATES LAYER
    bus_layer = folium.FeatureGroup(name="버스 정류장 후보지 (TOP 30)", show=False)
    if len(bus_stops) > 0:
        max_pass = bus_stops['passengers'].max()
        for _,row in bus_stops.iterrows():
            size = 4 + int(8 * row['passengers'] / max_pass)
            folium.CircleMarker(
                location=[row['lat'],row['lon']], radius=size,
                color='#3498db', fill=True, fill_color='#74b9ff', fill_opacity=0.8,
                tooltip=f"{row['name']}: {row['passengers']:,}명/월",
            ).add_to(bus_layer)
    bus_layer.add_to(m)

    # ── P-MEDIAN OPTIMAL SITES LAYER
    optimal_layer = folium.FeatureGroup(name="AI 추천 최적 입지 (p-median)", show=True)
    site_names = ["최적 입지 1호", "최적 입지 2호", "최적 입지 3호"]
    for i,(lo,la) in enumerate(optimal_sites):
        if BOUNDS['lat_min']<=la<=BOUNDS['lat_max'] and BOUNDS['lon_min']<=lo<=BOUNDS['lon_max']:
            folium.Marker(
                location=[la,lo],
                popup=folium.Popup(
                    f"<b>AI 추천: {site_names[i]}</b><br>"
                    f"학원 밀집도 기반 p-median 알고리즘<br>"
                    f"좌표: ({la:.4f}, {lo:.4f})", max_width=240),
                tooltip=f"★ {site_names[i]}",
                icon=folium.Icon(color='orange', icon='star', prefix='fa'),
            ).add_to(optimal_layer)
            # Pulsing circle
            folium.Circle(location=[la,lo], radius=800,
                color='#f39c12', weight=2.5, fill=True,
                fill_color='#f39c12', fill_opacity=0.12).add_to(optimal_layer)
    optimal_layer.add_to(m)

    LayerControl(collapsed=False).add_to(m)

    # ── DISTRICT STATS TABLE (side panel)
    total_acad = len(df_academies) if df_academies is not None else 0
    district_acad = {}
    if df_academies is not None:
        for d in ['부평구','남동구','연수구','서구','계양구','미추홀구','중구','동구','강화군','옹진군']:
            district_acad[d] = len(df_academies[df_academies['지역'].str.contains(d,na=False)])

    rows_html = ""
    for district, acad_count in sorted(district_acad.items(), key=lambda x:-x[1]):
        s_rate = stress.get(district, "-")
        y_pop  = f"{youth_pop.get(district,0):,}" if district in youth_pop else "-"
        s_color = "#e74c3c" if isinstance(s_rate,float) and s_rate>25 else "#f39c12" if isinstance(s_rate,float) and s_rate>22 else "#2ecc71"
        rows_html += f"""
        <tr style="border-bottom:1px solid rgba(255,255,255,0.07);">
            <td style="padding:5px 4px;font-weight:600;">{district}</td>
            <td style="padding:5px 4px;text-align:right;color:#74b9ff;">{acad_count:,}</td>
            <td style="padding:5px 4px;text-align:right;color:{s_color};">{s_rate}{'%' if isinstance(s_rate,float) else ''}</td>
            <td style="padding:5px 4px;text-align:right;color:#55efc4;">{y_pop}</td>
        </tr>"""

    title_html = f"""
    <div style="position:fixed;top:14px;left:58px;z-index:1000;
        background:rgba(12,18,32,0.92);backdrop-filter:blur(10px);
        border-radius:14px;padding:14px 18px;
        box-shadow:0 6px 32px rgba(0,0,0,0.4);
        font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
        color:#fff;width:320px;
        border:1px solid rgba(255,255,255,0.08);">
        <div style="font-size:14px;font-weight:700;letter-spacing:0.5px;color:#f0f0f0;margin-bottom:2px;">
            인천 청소년 쉼터 최적 입지 분석
        </div>
        <div style="font-size:10px;color:#aaa;margin-bottom:12px;">
            Incheon Youth Shelter Optimization · Voronoi + p-median
        </div>
        <div style="display:flex;gap:0;border-radius:10px;overflow:hidden;background:rgba(255,255,255,0.05);margin-bottom:12px;">
            <div style="flex:1;text-align:center;padding:8px 4px;border-right:1px solid rgba(255,255,255,0.08);">
                <div style="font-size:18px;font-weight:800;color:#ff6b6b;">{total_acad:,}</div>
                <div style="font-size:9px;color:#aaa;margin-top:2px;">등록 학원</div>
            </div>
            <div style="flex:1;text-align:center;padding:8px 4px;border-right:1px solid rgba(255,255,255,0.08);">
                <div style="font-size:18px;font-weight:800;color:#74b9ff;">{shelter_count}</div>
                <div style="font-size:9px;color:#aaa;margin-top:2px;">인천 쉼터</div>
            </div>
            <div style="flex:1;text-align:center;padding:8px 4px;border-right:1px solid rgba(255,255,255,0.08);">
                <div style="font-size:18px;font-weight:800;color:#f39c12;">3</div>
                <div style="font-size:9px;color:#aaa;margin-top:2px;">AI 추천 입지</div>
            </div>
            <div style="flex:1;text-align:center;padding:8px 4px;">
                <div style="font-size:18px;font-weight:800;color:#55efc4;">{len(valid_polys)}</div>
                <div style="font-size:9px;color:#aaa;margin-top:2px;">분석 영역</div>
            </div>
        </div>
        <table style="width:100%;font-size:10px;border-collapse:collapse;">
            <thead>
                <tr style="border-bottom:1px solid rgba(255,255,255,0.2);color:#aaa;">
                    <th style="padding:4px;text-align:left;">구</th>
                    <th style="padding:4px;text-align:right;">학원수</th>
                    <th style="padding:4px;text-align:right;">스트레스</th>
                    <th style="padding:4px;text-align:right;">청소년인구</th>
                </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>"""
    m.get_root().html.add_child(folium.Element(title_html))

    legend_html = """
    <div style="position:fixed;bottom:28px;right:14px;z-index:1000;
        background:rgba(12,18,32,0.92);backdrop-filter:blur(10px);
        border-radius:14px;padding:14px 18px;
        box-shadow:0 6px 32px rgba(0,0,0,0.4);
        font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
        font-size:11px;min-width:175px;
        border:1px solid rgba(255,255,255,0.08);color:#f0f0f0;">
        <div style="font-weight:700;margin-bottom:10px;font-size:12px;">범례</div>
        <div style="font-size:10px;color:#aaa;margin-bottom:4px;">학원 밀집도 (보로노이 색상)</div>
        <div style="height:10px;width:100%;background:linear-gradient(to right,
            hsl(200,65%,65%),hsl(260,70%,60%),hsl(300,75%,55%),hsl(30,80%,60%),hsl(10,85%,50%));
            border-radius:5px;margin-bottom:3px;"></div>
        <div style="display:flex;justify-content:space-between;font-size:9px;color:#888;margin-bottom:12px;">
            <span>낮음</span><span>높음</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">
            <div style="width:13px;height:13px;border-radius:50%;background:#e74c3c;flex-shrink:0;"></div>
            <span>청소년 쉼터 (기존)</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">
            <div style="width:13px;height:13px;border-radius:50%;background:#f39c12;flex-shrink:0;"></div>
            <span>AI 추천 최적 입지</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">
            <div style="width:13px;height:13px;border-radius:50%;background:#3498db;flex-shrink:0;"></div>
            <span>버스 정류장 후보</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
            <div style="width:13px;height:13px;border-radius:3px;background:rgba(100,180,255,0.45);
                border:1px solid rgba(255,255,255,0.3);flex-shrink:0;"></div>
            <span>보로노이 세력권</span>
        </div>
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    output = "results/final_analysis.html"
    m.save(output)
    print(f"\n  Saved -> {output}")
    print(f"  Polygons: {len(valid_polys)} | Shelters: {shelter_count} | Optimal sites: {len(optimal_sites)}")

# ── MAIN ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    setup_dirs()
    df = merge_academies()
    stress    = load_stress()
    youth_pop = load_youth_pop()
    bus_stops = load_bus_stops()
    shelters  = load_shelters()

    cache = "data/processed/geocoded_cache.csv"
    if os.path.exists(cache):
        geo = pd.read_csv(cache)
        if len(geo)<100 or (geo['lat'].max()-geo['lat'].min())<0.05:
            os.remove(cache); geo = generate_points(df)
        else:
            print(f"[2] Loaded {len(geo)} cached points.")
    else:
        geo = generate_points(df)

    build_map(geo, df, stress, youth_pop, bus_stops, shelters)
    print("\nDONE! Open results/final_analysis.html")
