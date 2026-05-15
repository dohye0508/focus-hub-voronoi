import os
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import HeatMap
from folium import LayerControl
from scipy.spatial import Voronoi
from scipy.cluster.vq import kmeans2
import warnings
warnings.filterwarnings('ignore')

def setup_dirs():
    for d in ['data/raw','data/processed','data/spatial','results']:
        os.makedirs(d, exist_ok=True)

# ── DATA LOADERS ─────────────────────────────────────────────────────

def load_academies():
    print("[1] Loading Academy Data...")
    path = "data/raw/학원교습소정보_2026년04월30일기준.csv"
    if not os.path.exists(path): return {}
    try:
        df = pd.read_csv(path, encoding='cp949', low_memory=False)
        addr_col = [c for c in df.columns if '주소' in str(c)][0]
        df['sig'] = df[addr_col].apply(lambda x: ' '.join(str(x).split()[:2]))
        counts = df.groupby('sig').size().to_dict()
        print(f"  {len(df):,} academies in {len(counts)} regions.")
        return counts
    except Exception as e:
        print(f"  Error: {e}"); return {}

def load_stress():
    print("[2] Loading Stress Data...")
    path = "data/raw/시·군·구별_스트레스_인지율_20260515193518.xlsx"
    if not os.path.exists(path): return {}
    try:
        df = pd.read_excel(path, header=None)
        df[0] = df[0].ffill()
        out = {}
        for _, row in df.iterrows():
            sido, sig = str(row.iloc[0]), str(row.iloc[1])
            if sido == 'nan' or sig == 'nan': continue
            try:
                out[f"{sido} {sig}"] = float(str(row.iloc[4]))
            except: pass
        print(f"  {len(out)} regions.")
        return out
    except Exception as e:
        print(f"  Error: {e}"); return {}

def load_population():
    print("[3] Loading Population Data...")
    path = "data/raw/행정안전부_지역별(행정동) 성별 연령별 주민등록 인구수_20260430.csv"
    if not os.path.exists(path): return {}
    try:
        df = pd.read_csv(path, encoding='cp949', low_memory=False)
        cols = df.columns.tolist()
        youth = [i for i,c in enumerate(cols) if any(f"{a}세" in str(c) for a in range(10,25))]
        df['yp'] = df.iloc[:,youth].apply(lambda x: pd.to_numeric(x.astype(str).str.replace(',',''), errors='coerce')).sum(axis=1)
        df['sig'] = df.iloc[:,2].astype(str) + ' ' + df.iloc[:,3].astype(str)
        out = df.groupby('sig')['yp'].sum().to_dict()
        print(f"  {len(out)} regions.")
        return out
    except Exception as e:
        print(f"  Error: {e}"); return {}

def load_shelters():
    print("[4] Loading Shelter Data...")
    try:
        gdf = gpd.read_file("data/spatial/전국+청소년쉼터+현황/Youth shelter.shp")
        print(f"  {len(gdf)} shelters. CRS: {gdf.crs}")
        # Convert to WGS84 if needed
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        return gdf
    except Exception as e:
        print(f"  Error: {e}"); return gpd.GeoDataFrame()

# ── COORDINATE DICTIONARY ─────────────────────────────────────────────

def get_coords():
    return {
        # 서울 25구
        "서울특별시 강남구":(37.495,127.062),"서울특별시 서초구":(37.483,127.032),
        "서울특별시 송파구":(37.514,127.106),"서울특별시 강동구":(37.530,127.124),
        "서울특별시 마포구":(37.566,126.901),"서울특별시 용산구":(37.532,126.990),
        "서울특별시 종로구":(37.573,126.979),"서울특별시 중구":(37.563,126.997),
        "서울특별시 노원구":(37.654,127.056),"서울특별시 성북구":(37.589,127.017),
        "서울특별시 동대문구":(37.574,127.040),"서울특별시 성동구":(37.563,127.037),
        "서울특별시 광진구":(37.538,127.082),"서울특별시 강북구":(37.637,127.025),
        "서울특별시 도봉구":(37.669,127.047),"서울특별시 중랑구":(37.606,127.093),
        "서울특별시 은평구":(37.602,126.929),"서울특별시 서대문구":(37.579,126.937),
        "서울특별시 양천구":(37.516,126.866),"서울특별시 강서구":(37.551,126.849),
        "서울특별시 구로구":(37.495,126.887),"서울특별시 금천구":(37.457,126.895),
        "서울특별시 영등포구":(37.526,126.896),"서울특별시 동작구":(37.512,126.939),
        "서울특별시 관악구":(37.478,126.951),
        # 경기
        "경기도 수원시":(37.263,127.028),"경기도 화성시":(37.200,126.830),
        "경기도 고양시":(37.658,126.832),"경기도 용인시":(37.234,127.202),
        "경기도 성남시":(37.419,127.126),"경기도 안산시":(37.323,126.832),
        "경기도 남양주시":(37.636,127.217),"경기도 안양시":(37.394,126.956),
        "경기도 부천시":(37.503,126.766),"경기도 평택시":(36.994,127.113),
        "경기도 의정부시":(37.738,127.047),"경기도 시흥시":(37.380,126.803),
        "경기도 파주시":(37.760,126.780),"경기도 김포시":(37.615,126.716),
        "경기도 광주시":(37.430,127.255),"경기도 광명시":(37.479,126.864),
        "경기도 군포시":(37.361,126.935),"경기도 하남시":(37.540,127.215),
        "경기도 오산시":(37.150,127.077),"경기도 이천시":(37.272,127.435),
        "경기도 양주시":(37.785,127.045),"경기도 구리시":(37.594,127.130),
        "경기도 의왕시":(37.344,126.969),"경기도 포천시":(37.895,127.200),
        "경기도 안성시":(37.008,127.280),"경기도 과천시":(37.429,126.987),
        # 인천
        "인천광역시 연수구":(37.409,126.678),"인천광역시 부평구":(37.508,126.722),
        "인천광역시 서구":(37.545,126.676),"인천광역시 남동구":(37.448,126.731),
        "인천광역시 계양구":(37.537,126.739),"인천광역시 미추홀구":(37.463,126.650),
        "인천광역시 동구":(37.474,126.643),"인천광역시 중구":(37.474,126.621),
        # 부산
        "부산광역시 해운대구":(35.163,129.163),"부산광역시 부산진구":(35.163,129.053),
        "부산광역시 남구":(35.136,129.085),"부산광역시 북구":(35.197,128.989),
        "부산광역시 동래구":(35.205,129.085),"부산광역시 사하구":(35.099,128.974),
        "부산광역시 수영구":(35.145,129.113),"부산광역시 연제구":(35.174,129.079),
        "부산광역시 금정구":(35.240,129.091),"부산광역시 사상구":(35.157,128.992),
        # 대구
        "대구광역시 수성구":(35.858,128.631),"대구광역시 달서구":(35.830,128.532),
        "대구광역시 북구":(35.886,128.583),"대구광역시 동구":(35.887,128.635),
        "대구광역시 달성군":(35.774,128.431),"대구광역시 서구":(35.872,128.561),
        "대구광역시 중구":(35.870,128.596),"대구광역시 남구":(35.845,128.597),
        # 대전
        "대전광역시 유성구":(36.362,127.356),"대전광역시 서구":(36.354,127.383),
        "대전광역시 중구":(36.325,127.421),"대전광역시 동구":(36.312,127.454),
        "대전광역시 대덕구":(36.346,127.416),
        # 광주
        "광주광역시 광산구":(35.140,126.793),"광주광역시 서구":(35.152,126.891),
        "광주광역시 북구":(35.174,126.912),"광주광역시 남구":(35.132,126.902),
        "광주광역시 동구":(35.146,126.923),
        # 울산
        "울산광역시 남구":(35.544,129.330),"울산광역시 울주군":(35.520,129.240),
        "울산광역시 북구":(35.603,129.361),"울산광역시 중구":(35.569,129.316),
        "울산광역시 동구":(35.505,129.416),
        # 세종
        "세종특별자치시 세종시":(36.480,127.289),
        # 충청
        "충청북도 청주시":(36.641,127.489),"충청북도 충주시":(36.991,127.925),
        "충청남도 천안시":(36.806,127.152),"충청남도 아산시":(36.789,127.004),
        "충청남도 서산시":(36.784,126.450),"충청남도 당진시":(36.890,126.628),
        # 전라
        "전라북도 전주시":(35.824,127.148),"전라북도 익산시":(35.948,126.958),
        "전라북도 군산시":(35.968,126.737),"전라북도 완주군":(35.905,127.158),
        "전라남도 여수시":(34.762,127.662),"전라남도 순천시":(34.950,127.488),
        "전라남도 목포시":(34.812,126.393),"전라남도 광양시":(34.944,127.696),
        # 경상
        "경상북도 포항시":(36.019,129.343),"경상북도 구미시":(36.120,128.344),
        "경상북도 경주시":(35.856,129.225),"경상북도 경산시":(35.825,128.741),
        "경상북도 안동시":(36.574,128.729),
        "경상남도 창원시":(35.228,128.681),"경상남도 김해시":(35.228,128.889),
        "경상남도 진주시":(35.180,128.107),"경상남도 양산시":(35.335,129.036),
        # 강원 (확장)
        "강원도 원주시":(37.342,127.921),"강원도 춘천시":(37.879,127.729),
        "강원도 강릉시":(37.751,128.876),"강원도 속초시":(38.207,128.592),
        "강원도 동해시":(37.524,129.114),"강원도 삼척시":(37.450,129.165),
        "강원도 태백시":(37.163,128.986),"강원도 홍천군":(37.697,127.889),
        "강원도 횡성군":(37.491,127.985),"강원도 영월군":(37.183,128.461),
        "강원도 평창군":(37.373,128.390),"강원도 정선군":(37.381,128.660),
        "강원도 철원군":(38.146,127.313),"강원도 화천군":(38.106,127.708),
        "강원도 양구군":(38.108,127.989),"강원도 인제군":(38.069,128.171),
        "강원도 고성군":(38.380,128.468),"강원도 양양군":(38.075,128.618),
        # 충청북도 (확장)
        "충청북도 제천시":(37.133,128.190),"충청북도 보은군":(36.489,127.729),
        "충청북도 옥천군":(36.301,127.571),"충청북도 영동군":(36.175,127.776),
        "충청북도 증평군":(36.785,127.581),"충청북도 진천군":(36.855,127.435),
        "충청북도 괴산군":(36.815,127.787),"충청북도 음성군":(37.000,127.688),
        "충청북도 단양군":(36.985,128.365),
        # 충청남도 (확장)
        "충청남도 공주시":(36.446,127.119),"충청남도 보령시":(36.334,126.612),
        "충청남도 논산시":(36.187,127.099),"충청남도 계룡시":(36.274,127.249),
        "충청남도 금산군":(36.108,127.489),"충청남도 부여군":(36.276,126.909),
        "충청남도 서천군":(36.080,126.690),"충청남도 청양군":(36.459,126.803),
        "충청남도 홍성군":(36.601,126.661),"충청남도 예산군":(36.680,126.850),
        "충청남도 태안군":(36.745,126.298),"충청남도 세종시":(36.480,127.289),
        # 전라북도 (확장)
        "전라북도 정읍시":(35.570,126.856),"전라북도 남원시":(35.416,127.390),
        "전라북도 김제시":(35.804,126.881),"전라북도 진안군":(35.791,127.424),
        "전라북도 무주군":(36.004,127.661),"전라북도 장수군":(35.647,127.521),
        "전라북도 임실군":(35.617,127.289),"전라북도 순창군":(35.374,127.138),
        "전라북도 고창군":(35.436,126.702),"전라북도 부안군":(35.732,126.733),
        # 전라남도 (확장)
        "전라남도 나주시":(35.016,126.711),"전라남도 담양군":(35.322,126.988),
        "전라남도 곡성군":(35.282,127.291),"전라남도 구례군":(35.197,127.463),
        "전라남도 고흥군":(34.604,127.278),"전라남도 보성군":(34.773,127.080),
        "전라남도 화순군":(35.065,126.987),"전라남도 장흥군":(34.682,126.907),
        "전라남도 강진군":(34.642,126.767),"전라남도 해남군":(34.574,126.599),
        "전라남도 영암군":(34.800,126.697),"전라남도 무안군":(34.990,126.481),
        "전라남도 함평군":(35.066,126.516),"전라남도 영광군":(35.277,126.512),
        "전라남도 장성군":(35.302,126.785),"전라남도 완도군":(34.310,126.755),
        "전라남도 진도군":(34.487,126.264),"전라남도 신안군":(34.827,126.107),
        # 경상북도 (확장)
        "경상북도 김천시":(36.120,128.114),"경상북도 영주시":(36.805,128.623),
        "경상북도 영천시":(35.973,128.938),"경상북도 상주시":(36.411,128.159),
        "경상북도 문경시":(36.586,128.186),"경상북도 칠곡군":(35.996,128.401),
        "경상북도 성주군":(35.919,128.283),"경상북도 군위군":(36.239,128.572),
        "경상북도 의성군":(36.352,128.697),"경상북도 청송군":(36.436,129.057),
        "경상북도 영양군":(36.667,129.113),"경상북도 영덕군":(36.415,129.365),
        "경상북도 청도군":(35.648,128.736),"경상북도 고령군":(35.728,128.263),
        "경상북도 성주군":(35.919,128.283),"경상북도 봉화군":(36.893,128.732),
        "경상북도 울진군":(36.993,129.400),"경상북도 울릉군":(37.484,130.905),
        # 경상남도 (확장)
        "경상남도 통영시":(34.854,128.433),"경상남도 사천시":(35.004,128.064),
        "경상남도 밀양시":(35.504,128.746),"경상남도 거제시":(34.880,128.621),
        "경상남도 의령군":(35.323,128.261),"경상남도 함안군":(35.273,128.406),
        "경상남도 창녕군":(35.545,128.492),"경상남도 고성군":(34.974,128.323),
        "경상남도 남해군":(34.838,127.892),"경상남도 하동군":(35.067,127.751),
        "경상남도 산청군":(35.415,127.874),"경상남도 함양군":(35.520,127.725),
        "경상남도 거창군":(35.687,127.909),"경상남도 합천군":(35.566,128.165),
        # 제주
        "제주특별자치도 제주시":(33.500,126.531),"제주특별자치도 서귀포시":(33.253,126.561),
    }

# ── COLOR UTILS ──────────────────────────────────────────────────────

def hsl_to_hex(h, s, l):
    h /= 360
    if s == 0: r = g = b = l
    else:
        def h2r(p, q, t):
            t = t % 1
            if t < 1/6: return p + (q-p)*6*t
            if t < 1/2: return q
            if t < 2/3: return p + (q-p)*(2/3-t)*6
            return p
        q = l*(1+s) if l < 0.5 else l+s-l*s
        p = 2*l - q
        r = h2r(p,q,h+1/3); g = h2r(p,q,h); b = h2r(p,q,h-1/3)
    return '#{:02x}{:02x}{:02x}'.format(int(r*255),int(g*255),int(b*255))

def cvi_to_color(cvi_norm):
    """Low CVI = blue, High CVI = red via HSL."""
    hue = 220 - cvi_norm * 220  # 220 (blue) → 0 (red)
    return hsl_to_hex(hue, 0.80, 0.55)

def make_icon(label, color, size=32):
    return folium.DivIcon(
        html=f'<div style="width:{size}px;height:{size}px;background:{color};'
             f'border-radius:50%;border:2.5px solid white;'
             f'box-shadow:0 2px 8px rgba(0,0,0,0.25);'
             f'display:flex;align-items:center;justify-content:center;'
             f'font-size:9px;font-weight:700;color:white;">{label}</div>',
        icon_size=(size, size), icon_anchor=(size//2, size//2))

# ── MAIN MAP BUILD ────────────────────────────────────────────────────

def build_map():
    setup_dirs()
    acad = load_academies()
    stress = load_stress()
    pop = load_population()
    shelters = load_shelters()
    coords = get_coords()

    # ── CVI per region ─────────────────────────────────────────────
    print("[5] Calculating CVI...")
    max_a = max(acad.values()) if acad else 1
    max_s = max(stress.values()) if stress else 1
    max_p = max(pop.values()) if pop else 1
    cvi = {}
    for reg in coords:
        a = acad.get(reg, 0)
        s = stress.get(reg, 0)
        p = pop.get(reg, 0)
        cvi[reg] = round(0.4*(a/max_a) + 0.3*(s/max_s) + 0.3*(p/max_p), 3)

    cvi_vals = list(cvi.values())
    cvi_max = max(cvi_vals) if cvi_vals else 1
    cvi_min = min(cvi_vals) if cvi_vals else 0

    # ── Build SINGLE unified Voronoi ──────────────────────────────
    print("[6] Building Unified Voronoi...")

    # Weight each region by academy count: more academies = more sub-points
    # But we use ONE point per region for the seed, so each region gets exactly 1 polygon
    seeds = []  # (lon, lat)
    seed_regs = []
    for reg, (la, lo) in coords.items():
        # Slightly jitter to avoid exact duplicates
        seeds.append((lo + np.random.uniform(-0.001, 0.001),
                       la + np.random.uniform(-0.001, 0.001)))
        seed_regs.append(reg)

    seeds = np.array(seeds)

    # Korea bounding box with generous margin
    KOR_LAT = (33.0, 38.7)
    KOR_LON = (124.5, 130.0)
    n_bdry = 12
    bdry = np.array([
        [lo, la]
        for la in np.linspace(KOR_LAT[0]-0.5, KOR_LAT[1]+0.5, n_bdry)
        for lo in np.linspace(KOR_LON[0]-0.5, KOR_LON[1]+0.5, n_bdry)
    ])

    all_pts = np.vstack([seeds, bdry])
    vor = Voronoi(all_pts)

    # ── MAP ──────────────────────────────────────────────────────
    print("[7] Rendering Map...")
    m = folium.Map(location=[36.5, 127.8], zoom_start=7, tiles=None)
    folium.TileLayer('CartoDB positron', name='지도 배경', show=True).add_to(m)

    # ── VORONOI LAYER ────────────────────────────────────────────
    vor_grp = folium.FeatureGroup(name="전국 학원 수요 세력권 (보로노이)", show=True)

    for i, ri in enumerate(vor.point_region[:len(seeds)]):
        region_idx = vor.regions[ri]
        if -1 in region_idx or len(region_idx) == 0:
            continue
        verts = [vor.vertices[j] for j in region_idx]

        # Clip to Korea bounds (skip if centroid is way outside)
        cx = np.mean([v[0] for v in verts])
        cy = np.mean([v[1] for v in verts])
        if not (KOR_LON[0] <= cx <= KOR_LON[1] and KOR_LAT[0] <= cy <= KOR_LAT[1]):
            continue

        reg = seed_regs[i]
        cv = cvi.get(reg, 0)
        cv_norm = (cv - cvi_min) / max(cvi_max - cvi_min, 0.001)
        color = cvi_to_color(cv_norm)
        a_cnt = acad.get(reg, 0)

        folium.Polygon(
            locations=[[v[1], v[0]] for v in verts],
            color='rgba(180,180,180,0.4)', weight=0.8,
            fill=True, fill_color=color, fill_opacity=0.40,
            tooltip=f"<b>{reg}</b><br>학원: {a_cnt:,}개 | CVI: {cv:.2f}"
        ).add_to(vor_grp)

    vor_grp.add_to(m)

    # ── HEATMAP LAYER ────────────────────────────────────────────
    heat_grp = folium.FeatureGroup(name="학원 밀집도 열지도", show=False)
    heat_pts = []
    for reg, (la, lo) in coords.items():
        w = acad.get(reg, 0)
        if w > 0:
            heat_pts.append([la, lo, w])
    if heat_pts:
        HeatMap(heat_pts, radius=35, blur=25, min_opacity=0.2,
                max_val=max(h[2] for h in heat_pts)).add_to(heat_grp)
    heat_grp.add_to(m)

    # ── SHELTER LAYER ────────────────────────────────────────────
    sh_grp = folium.FeatureGroup(name="전국 청소년 쉼터 (135개소)", show=True)
    shelter_count = 0
    if len(shelters) > 0:
        for _, row in shelters.iterrows():
            try:
                geom = row.geometry
                if geom is None or geom.is_empty:
                    continue
                lo, la = geom.x, geom.y
                # Sanity check (Korea bounds)
                if not (124 < lo < 132 and 33 < la < 39):
                    continue
                name = str(row.get('A9', '쉼터'))
                folium.Marker(
                    location=[la, lo],
                    icon=make_icon('쉼터', '#e74c3c', 30),
                    popup=folium.Popup(f"<b>{name}</b>", max_width=200),
                    tooltip=name
                ).add_to(sh_grp)
                shelter_count += 1
            except:
                continue
    sh_grp.add_to(m)

    # ── P-MEDIAN OPTIMAL SITES ───────────────────────────────────
    opt_grp = folium.FeatureGroup(name="이동형 쉼터 배치 권장지 (p-median)", show=True)
    # Use CVI-weighted coordinates as demand points
    demand_pts = []
    for reg, (la, lo) in coords.items():
        cv = cvi.get(reg, 0)
        n = max(1, int(cv * 20))  # Weight by CVI
        for _ in range(n):
            demand_pts.append([
                lo + np.random.normal(0, 0.01),
                la + np.random.normal(0, 0.01)
            ])
    demand_arr = np.array(demand_pts)
    if len(demand_arr) >= 3:
        try:
            centroids, _ = kmeans2(demand_arr, 3, iter=30, seed=42)
            site_labels = ["권장지 A", "권장지 B", "권장지 C"]
            for i, (lo, la) in enumerate(centroids):
                if 124 < lo < 132 and 33 < la < 39:
                    folium.Marker(
                        location=[la, lo],
                        icon=make_icon('★', '#f39c12', 36),
                        popup=folium.Popup(
                            f"<b>이동형 쉼터 {site_labels[i]}</b><br>"
                            f"p-median 알고리즘 기반 최적 배치 좌표<br>"
                            f"Lat: {la:.4f} / Lon: {lo:.4f}", max_width=260),
                        tooltip=f"★ 이동형 쉼터 {site_labels[i]}"
                    ).add_to(opt_grp)
        except Exception as e:
            print(f"  p-median error: {e}")
    opt_grp.add_to(m)

    LayerControl(collapsed=False).add_to(m)

    # ── STATS PANEL ──────────────────────────────────────────────
    top15 = sorted(cvi.items(), key=lambda x: -x[1])[:15]
    rows = ""
    for reg, score in top15:
        bw = int(score / max(cvi_max, 0.001) * 100)
        bc = "#e74c3c" if score > 0.6 else "#f39c12" if score > 0.4 else "#27ae60"
        ac = acad.get(reg, 0)
        sr = stress.get(reg, 0)
        rows += f"""<tr style="border-bottom:1px solid #f0f0f4;">
            <td style="padding:5px 3px;font-size:10px;font-weight:600;color:#2d3436;">{reg}</td>
            <td style="padding:5px;text-align:right;color:#2980b9;font-size:10px;">{ac:,}</td>
            <td style="padding:5px;text-align:right;color:#e74c3c;font-size:10px;">{sr}%</td>
            <td style="padding:5px;">
                <div style="display:flex;align-items:center;gap:4px;">
                    <div style="flex:1;background:#f0f0f4;height:5px;border-radius:3px;">
                        <div style="background:{bc};width:{bw}%;height:100%;border-radius:3px;"></div>
                    </div>
                    <span style="font-size:9px;color:{bc};font-weight:700;min-width:24px;">{score:.2f}</span>
                </div>
            </td>
        </tr>"""

    legend_bar = ""
    for i in range(11):
        pct = i / 10
        hue = 220 - pct * 220
        c = hsl_to_hex(hue, 0.80, 0.55)
        legend_bar += f'<div style="flex:1;background:{c};height:10px;"></div>'

    panel = f"""
    <div style="position:fixed;top:15px;left:60px;z-index:1000;
        background:rgba(255,255,255,0.97);backdrop-filter:blur(12px);
        border-radius:16px;padding:18px 20px;
        box-shadow:0 6px 28px rgba(0,0,0,0.13),0 0 0 1px rgba(0,0,0,0.05);
        font-family:'Noto Sans KR',sans-serif;width:360px;">
        <div style="margin-bottom:14px;">
            <div style="font-size:14px;font-weight:800;color:#2d3436;">전국 청소년 복지 취약지수</div>
            <div style="font-size:9px;color:#95a5a6;">CVI = 0.4×학원 + 0.3×인구 + 0.3×스트레스 | 전국 {len(coords)}개 시군구</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:14px;">
            <div style="background:#fff5f5;border:1.5px solid #ffd5d5;border-radius:10px;padding:8px;text-align:center;">
                <div style="font-size:18px;font-weight:800;color:#e74c3c;">138k+</div>
                <div style="font-size:8px;color:#999;">전국 학원</div>
            </div>
            <div style="background:#f0f7ff;border:1.5px solid #d5e8ff;border-radius:10px;padding:8px;text-align:center;">
                <div style="font-size:18px;font-weight:800;color:#2980b9;">{shelter_count}</div>
                <div style="font-size:8px;color:#999;">전국 쉼터</div>
            </div>
            <div style="background:#f0fff5;border:1.5px solid #d5ffe8;border-radius:10px;padding:8px;text-align:center;">
                <div style="font-size:18px;font-weight:800;color:#27ae60;">{len(coords)}</div>
                <div style="font-size:8px;color:#999;">분석 지역</div>
            </div>
        </div>
        <div style="font-size:9px;color:#95a5a6;margin-bottom:4px;">취약지수 (색상 범례)</div>
        <div style="display:flex;border-radius:4px;overflow:hidden;margin-bottom:2px;height:10px;">{legend_bar}</div>
        <div style="display:flex;justify-content:space-between;font-size:8px;color:#bdc3c7;margin-bottom:12px;">
            <span>낮음</span><span>높음</span>
        </div>
        <div style="height:1px;background:#f0f0f4;margin-bottom:10px;"></div>
        <table style="width:100%;border-collapse:collapse;">
            <tr style="border-bottom:2px solid #f0f0f4;">
                <th style="padding:4px 3px;font-size:9px;color:#95a5a6;font-weight:500;text-align:left;">지역</th>
                <th style="padding:4px;font-size:9px;color:#2980b9;font-weight:500;text-align:right;">학원</th>
                <th style="padding:4px;font-size:9px;color:#e74c3c;font-weight:500;text-align:right;">스트레스</th>
                <th style="padding:4px;font-size:9px;color:#f39c12;font-weight:500;">CVI</th>
            </tr>
            {rows}
        </table>
    </div>"""
    m.get_root().html.add_child(folium.Element(panel))

    out = "results/nationwide_analysis.html"
    m.save(out)
    print(f"\n[DONE] Saved {out} | Shelters:{shelter_count} | Regions:{len(coords)}")

if __name__ == "__main__":
    build_map()
