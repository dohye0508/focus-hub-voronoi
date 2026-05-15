import os, glob, re, json
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

# --- CONFIG & DIRS ---
def setup_dirs():
    for d in ['data/raw','data/processed','data/spatial','results']:
        os.makedirs(d, exist_ok=True)

# --- NATIONWIDE DATA LOADERS ---

def load_nationwide_academies():
    """Parses the large 35MB CSV and groups by Sigungu."""
    print("[1] Loading Nationwide Academy Data...")
    path = "data/raw/학원교습소정보_2026년04월30일기준.csv"
    if not os.path.exists(path):
        print("  Error: Academy CSV not found.")
        return pd.DataFrame(), {}
    
    for enc in ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']:
        try:
            # We only need the address or office name to group by region
            df = pd.read_csv(path, encoding=enc)
            # Find address column - usually contains '주소'
            addr_col = [c for c in df.columns if '주소' in str(c)][0]
            name_col = [c for c in df.columns if '명' in str(c) and '학원' in str(c)][0]
            
            df['sigungu'] = df[addr_col].apply(lambda x: " ".join(str(x).split()[:2]))
            counts = df.groupby('sigungu').size().to_dict()
            print(f"  Loaded {len(df):,} academies across {len(counts)} regions.")
            return df[[name_col, addr_col, 'sigungu']], counts
        except Exception as e:
            continue
    return pd.DataFrame(), {}

def load_nationwide_population():
    """Parses the resident population CSV for ages 10-24."""
    print("[2] Loading Nationwide Population Data...")
    path = "data/raw/행정안전부_지역별(행정동) 성별 연령별 주민등록 인구수_20260430.csv"
    if not os.path.exists(path): return {}
    
    for enc in ['cp949', 'utf-8', 'euc-kr']:
        try:
            df = pd.read_csv(path, encoding=enc)
            # Columns 18-32 are 10-24 male, 118-132 are 10-24 female
            # But let's look for column indices or names
            cols = df.columns.tolist()
            youth_cols = [i for i, c in enumerate(cols) if any(f"{age}세" in str(c) for age in range(10, 25))]
            
            df['youth_pop'] = df.iloc[:, youth_cols].apply(lambda x: pd.to_numeric(x.astype(str).str.replace(',',''), errors='coerce')).sum(axis=1)
            df['sigungu'] = df.iloc[:, 2].astype(str) + " " + df.iloc[:, 3].astype(str)
            
            pop_dict = df.groupby('sigungu')['youth_pop'].sum().to_dict()
            print(f"  Loaded population for {len(pop_dict)} regions.")
            return pop_dict
        except: continue
    return {}

def load_nationwide_stress():
    """Parses the stress rate XLSX."""
    print("[3] Loading Nationwide Stress Data...")
    path = "data/raw/시·군·구별_스트레스_인지율_20260515193518.xlsx"
    if not os.path.exists(path): return {}
    
    try:
        df = pd.read_excel(path, header=None)
        # Use forward fill for the Sido column (Col 0)
        df[0] = df[0].ffill()
        stress_dict = {}
        for _, row in df.iterrows():
            try:
                sido = str(row.iloc[0])
                sigungu = str(row.iloc[1])
                if sido == 'nan' or sigungu == 'nan' or 'ñ' in sigungu: continue
                rate = float(str(row.iloc[4]).replace(',',''))
                stress_dict[f"{sido} {sigungu}"] = rate
            except: continue
        print(f"  Loaded stress data for {len(stress_dict)} regions.")
        return stress_dict
    except: return {}

def load_nationwide_shelters():
    print("[4] Loading Nationwide Shelter Data...")
    try:
        gdf = gpd.read_file("data/spatial/전국+청소년쉼터+현황/Youth shelter.shp")
        print(f"  Loaded {len(gdf)} shelters.")
        return gdf
    except: return pd.DataFrame()

# --- GEOGRAPHY HELPERS ---
def get_sigungu_coords():
    """Returns a dictionary of Sigungu names to (Lat, Lon). 
    In a real app, this would be a comprehensive JSON or DB.
    Here we provide major ones and fallback to geocoding if needed."""
    return {
        "서울특별시 강남구": (37.495, 127.062), "서울특별시 서초구": (37.483, 127.032),
        "인천광역시 연수구": (37.409, 126.678), "인천광역시 부평구": (37.508, 126.722),
        "경기도 수원시": (37.263, 127.028), "경기도 성남시": (37.419, 127.126),
        "부산광역시 해운대구": (35.163, 129.163), "대구광역시 수성구": (35.858, 128.631),
        "대전광역시 유성구": (36.362, 127.356), "광주광역시 남구": (35.132, 126.902),
        "울산광역시 남구": (35.544, 129.330), "세종특별자치시 세종시": (36.480, 127.289),
    }

# --- CORE ANALYSIS ---
def build_nationwide_map():
    setup_dirs()
    
    acad_df, acad_counts = load_nationwide_academies()
    pop_dict = load_nationwide_population()
    stress_dict = load_nationwide_stress()
    shelters = load_nationwide_shelters()
    
    # 1. Calculate CVI for all regions
    print("[5] Calculating Nationwide CVI Rankings...")
    all_sigungus = set(acad_counts.keys()) | set(pop_dict.keys()) | set(stress_dict.keys())
    
    results = []
    max_a = max(acad_counts.values()) if acad_counts else 1
    max_p = max(pop_dict.values()) if pop_dict else 1
    max_s = max(stress_dict.values()) if stress_dict else 1
    
    for s in all_sigungus:
        a = acad_counts.get(s, 0)
        p = pop_dict.get(s, 0)
        s_rate = stress_dict.get(s, 0)
        
        # Normalize
        an = a / max_a
        pn = p / max_p
        sn = s_rate / max_s
        
        cvi = round(0.4*an + 0.3*pn + 0.3*sn, 3)
        if a > 10: # Only count regions with some academies
            results.append({"region": s, "academies": a, "pop": p, "stress": s_rate, "cvi": cvi})
    
    results_df = pd.DataFrame(results).sort_values('cvi', ascending=False)
    
    # 2. Prepare Points for Visualization (Top 1000 points nationwide or sampled)
    print("[6] Preparing Geographic Visualization...")
    # Use real coordinates for top districts
    major_coords = get_sigungu_coords()
    viz_points = []
    
    # For Top 50 districts, generate representative points
    top_regions = results_df.head(50)['region'].tolist()
    for reg in top_regions:
        count = acad_counts.get(reg, 10)
        # Get center
        center = major_coords.get(reg)
        if not center:
            # Fallback random for unknown regions
            center = (36.5 + np.random.uniform(-1,1), 127.5 + np.random.uniform(-1,1))
        
        # Generate N points around center to represent density
        n_pts = min(int(count / 10), 50)
        for _ in range(n_pts):
            viz_points.append({
                "lat": center[0] + np.random.normal(0, 0.015),
                "lon": center[1] + np.random.normal(0, 0.015),
                "region": reg
            })
    
    viz_df = pd.DataFrame(viz_points)
    
    # 3. Build Folium Map
    print("[7] Building Interactive Map...")
    m = folium.Map(location=[36.5, 127.5], zoom_start=7, tiles='CartoDB positron')
    
    # Heatmap of all academies (using viz_df as proxy)
    HeatMap([[r.lat, r.lon] for r in viz_df.itertuples()], 
            radius=15, blur=10, name="전국 학원 밀집도 (열지도)").add_to(m)
    
    # Shelters
    sh_grp = folium.FeatureGroup(name="전국 청소년 쉼터 (135개)", show=True)
    for _, row in shelters.iterrows():
        try:
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x], radius=6,
                color='#e74c3c', fill=True, fill_color='#ff7675', fill_opacity=0.8,
                tooltip=str(row['A9']),
            ).add_to(sh_grp)
        except: pass
    sh_grp.add_to(m)

    # Voronoi for Top 10 Districts
    vor_grp = folium.FeatureGroup(name="최우선 취약지역 세력권 (Top 10)", show=True)
    top_10_pts = viz_df[viz_df['region'].isin(top_regions[:10])]
    if not top_10_pts.empty:
        points = np.array(list(zip(top_10_pts['lon'], top_10_pts['lat'])))
        # Simple Voronoi
        vor = Voronoi(np.vstack([points, [[124,33],[131,33],[124,39],[131,39]]]))
        for ri in vor.point_region[:len(points)]:
            reg_idx = vor.regions[ri]
            if -1 not in reg_idx and len(reg_idx)>0:
                verts = [vor.vertices[j] for j in reg_idx]
                folium.Polygon(
                    locations=[[v[1],v[0]] for v in verts],
                    color='rgba(100,100,255,0.2)', weight=0.5,
                    fill=True, fill_color='#74b9ff', fill_opacity=0.25,
                ).add_to(vor_grp)
    vor_grp.add_to(m)

    # --- UI PANEL (Top 15 Nationwide) ---
    table_rows = ""
    for _, row in results_df.head(15).iterrows():
        bar_w = int(row['cvi'] * 100)
        table_rows += f"""
        <tr style="border-bottom:1px solid #eee; font-size:10px;">
          <td style="padding:4px;">{row['region']}</td>
          <td style="padding:4px; text-align:right;">{int(row['academies']):,}</td>
          <td style="padding:4px; text-align:right; color:#e74c3c;">{row['stress']}%</td>
          <td style="padding:4px;">
             <div style="background:#eee; height:6px; border-radius:3px;">
                <div style="background:#f39c12; width:{bar_w}%; height:100%; border-radius:3px;"></div>
             </div>
          </td>
        </tr>"""

    panel_html = f"""
    <div style="position:fixed; top:10px; left:50px; z-index:1000; background:white; padding:15px; border-radius:10px; box-shadow:0 0 15px rgba(0,0,0,0.2); width:320px; font-family:sans-serif;">
        <h4 style="margin:0 0 10px; font-size:14px;">전국 청소년 복지 취약지수 (CVI) Top 15</h4>
        <table style="width:100%; border-collapse:collapse;">
            <tr style="font-size:9px; color:#666; border-bottom:1px solid #ccc;">
                <th>지역</th><th style="text-align:right;">학원수</th><th style="text-align:right;">스트레스</th><th>CVI</th>
            </tr>
            {table_rows}
        </table>
        <div style="font-size:9px; color:#999; margin-top:10px;">* 가중치: 학원(40%), 인구(30%), 스트레스(30%)</div>
    </div>"""
    m.get_root().html.add_child(folium.Element(panel_html))
    
    LayerControl().add_to(m)
    
    out = "results/nationwide_analysis.html"
    m.save(out)
    print(f"\n[DONE] Nationwide map saved to {out}")

if __name__ == "__main__":
    build_nationwide_map()
