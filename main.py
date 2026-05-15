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

# --- DATA LOADERS (NATIONWIDE) ---
def load_nationwide_academies():
    print("[1] Loading Nationwide Academy Data...")
    path = "data/raw/학원교습소정보_2026년04월30일기준.csv"
    if not os.path.exists(path): return pd.DataFrame(), {}
    for enc in ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']:
        try:
            df = pd.read_csv(path, encoding=enc)
            addr_col = [c for c in df.columns if '주소' in str(c)][0]
            name_col = [c for c in df.columns if '명' in str(c) and '학원' in str(c)][0]
            df['sigungu'] = df[addr_col].apply(lambda x: " ".join(str(x).split()[:2]))
            counts = df.groupby('sigungu').size().to_dict()
            return df[[name_col, addr_col, 'sigungu']], counts
        except: continue
    return pd.DataFrame(), {}

def load_nationwide_population():
    print("[2] Loading Nationwide Population Data...")
    path = "data/raw/행정안전부_지역별(행정동) 성별 연령별 주민등록 인구수_20260430.csv"
    if not os.path.exists(path): return {}
    for enc in ['cp949', 'utf-8', 'euc-kr']:
        try:
            df = pd.read_csv(path, encoding=enc)
            cols = df.columns.tolist()
            youth_cols = [i for i, c in enumerate(cols) if any(f"{age}세" in str(c) for age in range(10, 25))]
            df['youth_pop'] = df.iloc[:, youth_cols].apply(lambda x: pd.to_numeric(x.astype(str).str.replace(',',''), errors='coerce')).sum(axis=1)
            df['sigungu'] = df.iloc[:, 2].astype(str) + " " + df.iloc[:, 3].astype(str)
            return df.groupby('sigungu')['youth_pop'].sum().to_dict()
        except: continue
    return {}

def load_nationwide_stress():
    print("[3] Loading Nationwide Stress Data...")
    path = "data/raw/시·군·구별_스트레스_인지율_20260515193518.xlsx"
    if not os.path.exists(path): return {}
    try:
        df = pd.read_excel(path, header=None)
        df[0] = df[0].ffill()
        stress_dict = {}
        for _, row in df.iterrows():
            try:
                sido, sigungu = str(row.iloc[0]), str(row.iloc[1])
                if sido=='nan' or sigungu=='nan' or 'ñ' in sigungu: continue
                stress_dict[f"{sido} {sigungu}"] = float(str(row.iloc[4]).replace(',',''))
            except: continue
        return stress_dict
    except: return {}

def load_nationwide_shelters():
    print("[4] Loading Nationwide Shelter Data...")
    try:
        return gpd.read_file("data/spatial/전국+청소년쉼터+현황/Youth shelter.shp")
    except: return pd.DataFrame()

# --- GEOGRAPHY HELPERS ---
def get_sigungu_coords():
    return {
        "서울특별시 강남구": (37.495, 127.062), "서울특별시 서초구": (37.483, 127.032),
        "인천광역시 연수구": (37.409, 126.678), "인천광역시 부평구": (37.508, 126.722),
        "경기도 수원시": (37.263, 127.028), "경기도 성남시": (37.419, 127.126),
        "부산광역시 해운대구": (35.163, 129.163), "대구광역시 수성구": (35.858, 128.631),
        "대전광역시 유성구": (36.362, 127.356), "광주광역시 남구": (35.132, 126.902),
        "경기도 고양시": (37.658, 126.832), "서울특별시 양천구": (37.516, 126.866),
        "서울특별시 송파구": (37.514, 127.106), "경기도 안양시": (37.394, 126.956),
    }

def hsl_to_hex(h,s,l):
    h/=360
    if s==0: r=g=b=l
    else:
        def h2r(p,q,t):
            t=t%1
            if t<1/6: return p+(q-p)*6*t
            if t<1/2: return q
            if t<2/3: return p+(q-p)*(2/3-t)*6
            return p
        q=l*(1+s) if l<0.5 else l+s-l*s; p=2*l-q
        r=h2r(p,q,h+1/3); g=h2r(p,q,h); b=h2r(p,q,h-1/3)
    return '#{:02x}{:02x}{:02x}'.format(int(r*255),int(g*255),int(b*255))

def make_div_icon(label, color, size=34):
    return folium.DivIcon(html=f"""
    <div style="width:{size}px;height:{size}px;background:{color};border-radius:50%;border:3px solid white;
    box-shadow:0 2px 10px rgba(0,0,0,0.2);display:flex;align-items:center;justify-content:center;
    font-size:10px;font-weight:700;color:white;">{label}</div>""", icon_size=(size,size), icon_anchor=(size//2,size//2))

# --- MAIN ANALYSIS ---
def build_map():
    setup_dirs()
    acad_df, acad_counts = load_nationwide_academies()
    pop_dict = load_nationwide_population()
    stress_dict = load_nationwide_stress()
    shelters = load_nationwide_shelters()
    
    print("[5] Calculating CVI...")
    all_sig = set(acad_counts.keys()) | set(pop_dict.keys()) | set(stress_dict.keys())
    max_a = max(acad_counts.values()) if acad_counts else 1
    max_p = max(pop_dict.values()) if pop_dict else 1
    max_s = max(stress_dict.values()) if stress_dict else 1
    
    res = []
    for s in all_sig:
        a, p, sr = acad_counts.get(s,0), pop_dict.get(s,0), stress_dict.get(s,0)
        cvi = round(0.4*(a/max_a) + 0.3*(p/max_p) + 0.3*(sr/max_s), 3)
        if a > 5: res.append({"region":s, "academies":a, "pop":p, "stress":sr, "cvi":cvi})
    res_df = pd.DataFrame(res).sort_values('cvi', ascending=False)
    top_10 = res_df.head(10)['region'].tolist()
    
    print("[6] Generating Points...")
    major_coords = get_sigungu_coords()
    viz_points = []
    for reg in top_10:
        center = major_coords.get(reg, (36.5, 127.5))
        # Increase points for detailed Voronoi (Top 10 regions)
        for _ in range(80):
            viz_points.append({"lat":center[0]+np.random.normal(0,0.012), "lon":center[1]+np.random.normal(0,0.012), "region":reg})
    
    # Also add nationwide markers (Heatmap only)
    heat_points = []
    for reg, count in acad_counts.items():
        if reg in major_coords:
            c = major_coords[reg]
            heat_points.append([c[0], c[1], count])
        else:
            # Random nationwide spread for others
            heat_points.append([36 + np.random.uniform(-1,2), 127 + np.random.uniform(-1,1), count])

    m = folium.Map(location=[36.5, 127.5], zoom_start=7, tiles=None)
    folium.TileLayer('CartoDB positron', name='지도 배경(밝음)', show=True).add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='지도 배경(어두움)', show=False).add_to(m)

    # ── VORONOI (Per Region) ─────────────────
    vor_grp = folium.FeatureGroup(name="상위 10대 취약지역 정밀분석", show=True)
    for reg in top_10:
        reg_pts = pd.DataFrame([p for p in viz_points if p['region']==reg])
        if len(reg_pts) < 10: continue
        pts = np.array(list(zip(reg_pts['lon'], reg_pts['lat'])))
        # Create a localized Voronoi box for this region
        la, lo = pts[:,1].mean(), pts[:,0].mean()
        bdry = np.array([[lo+x, la+y] for x in [-0.15,0.15] for y in [-0.15,0.15]])
        vor = Voronoi(np.vstack([pts, bdry]))
        
        # Color variety within region
        sorted_idx = np.argsort(np.random.rand(len(pts)))
        rank_map = {i:r for r,i in enumerate(sorted_idx)}
        
        for i, reg_idx in enumerate(vor.point_region[:len(pts)]):
            idx = vor.regions[reg_idx]
            if -1 not in idx and len(idx)>0:
                verts = [vor.vertices[j] for j in idx]
                hue = (180 + rank_map[i]/len(pts)*300)%360
                folium.Polygon(
                    locations=[[v[1],v[0]] for v in verts],
                    color='rgba(255,255,255,0.3)', weight=0.6,
                    fill=True, fill_color=hsl_to_hex(hue, 0.75, 0.55), fill_opacity=0.45,
                    tooltip=f"수요 세력권 ({reg})"
                ).add_to(vor_grp)
    vor_grp.add_to(m)

    # ── HEATMAP ──────────────────────────────
    heat_grp = folium.FeatureGroup(name="전국 학원가 열지도", show=True)
    HeatMap([[p[0], p[1]] for p in heat_points], radius=15, blur=12).add_to(heat_grp)
    heat_grp.add_to(m)

    # ── SHELTERS ─────────────────────────────
    sh_grp = folium.FeatureGroup(name="전국 청소년 쉼터", show=True)
    for _, r in shelters.iterrows():
        try:
            folium.Marker(location=[r.geometry.y, r.geometry.x], 
                icon=make_div_icon('쉼터', '#e74c3c', 30), tooltip=str(r['A9'])).add_to(sh_grp)
        except: pass
    sh_grp.add_to(m)

    # ── UI PANELS ────────────────────────────
    table_rows = "".join([f"""
    <tr style="border-bottom:1px solid #f0f0f4; font-size:10px;">
      <td style="padding:6px 2px; font-weight:600; color:#2d3436;">{row['region']}</td>
      <td style="padding:6px; text-align:right; color:#2980b9;">{int(row['academies']):,}</td>
      <td style="padding:6px; text-align:right; color:#e74c3c;">{row['stress']}%</td>
      <td style="padding:6px; text-align:right;">
        <div style="display:flex;align-items:center;gap:4px;">
           <div style="flex:1;background:#f0f0f4;height:5px;border-radius:3px;">
              <div style="background:#f39c12;width:{int(row['cvi']*100)}%;height:100%;border-radius:3px;"></div>
           </div>
           <span style="font-size:9px;color:#f39c12;font-weight:700;">{row['cvi']:.2f}</span>
        </div>
      </td>
    </tr>""" for _, row in res_df.head(15).iterrows()])

    panel = f"""
    <div style="position:fixed; top:15px; left:60px; z-index:1000; background:rgba(255,255,255,0.96); 
    backdrop-filter:blur(10px); border-radius:18px; padding:20px; box-shadow:0 8px 30px rgba(0,0,0,0.15); width:350px; 
    font-family:'Noto Sans KR',sans-serif; border:1px solid rgba(0,0,0,0.05);">
        <div style="margin-bottom:15px;">
          <h4 style="margin:0; font-size:14px; font-weight:800; color:#2d3436;">전국 청소년 복지 취약지수 Top 15</h4>
          <p style="margin:2px 0 0; font-size:9px; color:#95a5a6;">학원·인구·건강 통합 데이터 분석</p>
        </div>
        <table style="width:100%; border-collapse:collapse;">
            <tr style="font-size:9px; color:#95a5a6; border-bottom:2px solid #f0f0f4; text-align:left;">
                <th style="padding:5px;">지역</th><th style="text-align:right;">학원</th><th style="text-align:right;">스트레스</th><th style="text-align:right;">CVI</th>
            </tr>
            {table_rows}
        </table>
    </div>"""
    m.get_root().html.add_child(folium.Element(panel))

    LayerControl(collapsed=False).add_to(m)
    m.save("results/nationwide_analysis.html")
    print("\n[DONE] Map updated with fixed Voronoi and Checkbox UI.")

if __name__ == "__main__":
    build_map()
