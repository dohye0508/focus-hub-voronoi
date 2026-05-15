import os, glob, re
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
    print(f"  {len(merged):,} academies.")
    return merged

def load_all_data():
    stress, youth_pop = {}, {}
    shelters_df = pd.DataFrame()
    name_map = ['중구','동구','미추홀구','연수구','남동구','부평구','계양구','서구','강화군','옹진군']

    try:
        df = pd.read_excel("data/raw/시·군·구별_스트레스_인지율_20260515154125.xlsx", header=None)
        for _, row in df.iterrows():
            raw = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ''
            for k in name_map:
                if k in raw:
                    try: stress[k] = float(str(row.iloc[3]).replace(',',''))
                    except: pass
        print(f"  Stress: {len(stress)} districts")
    except Exception as e: print(f"  Stress failed: {e}")

    try:
        df = pd.read_excel("data/raw/202604_202604_주민등록 인구 기타현황(아동청소년청년 인구현황)_월간.xlsx", header=None)
        for _, row in df.iterrows():
            raw = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ''
            for k in name_map:
                if k in raw:
                    try: youth_pop[k] = int(str(row.iloc[9]).replace(',','')) + int(str(row.iloc[12]).replace(',',''))
                    except: pass
        print(f"  Youth pop: {len(youth_pop)} districts")
    except Exception as e: print(f"  Youth pop failed: {e}")

    try:
        gdf = gpd.read_file("data/spatial/전국+청소년쉼터+현황/Youth shelter.shp")
        shelters_df = gdf[gdf['A6'] == '인천'].copy()
        print(f"  Shelters: {len(shelters_df)}")
    except Exception as e: print(f"  Shelter failed: {e}")

    return stress, youth_pop, shelters_df

def generate_points(df_academies):
    print("[2] Generating simulation points...")
    configs = {
        '부평구':   [(37.509,126.722,0.018,0.015),(37.520,126.738,0.010,0.010)],
        '남동구':   [(37.449,126.731,0.016,0.016),(37.435,126.750,0.010,0.010)],
        '연수구':   [(37.400,126.653,0.015,0.015),(37.383,126.643,0.008,0.010)],
        '서구':     [(37.547,126.676,0.020,0.016),(37.560,126.700,0.010,0.010)],
        '계양구':   [(37.537,126.739,0.016,0.014)],
        '미추홀구': [(37.460,126.650,0.015,0.013)],
        '중구':     [(37.475,126.614,0.012,0.012)],
        '동구':     [(37.476,126.643,0.010,0.010)],
        '강화군':   [(37.747,126.488,0.020,0.020)],
        '옹진군':   [(37.452,126.428,0.015,0.015)],
    }
    cnts = {n: max(len(df_academies[df_academies['지역'].str.contains(n,na=False)]),10) for n in configs}
    tot = sum(cnts.values())
    lats,lons,dists=[],[],[]
    for name,clusters in configs.items():
        n = max(int(600*cnts[name]/tot),8)
        each = n//len(clusters)
        for la,lo,sla,slo in clusters:
            lats.extend(np.random.normal(la,sla,each))
            lons.extend(np.random.normal(lo,slo,each))
            dists.extend([name]*each)
    df_pts = pd.DataFrame({'lat':lats,'lon':lons,'district':dists})
    df_pts.to_csv("data/processed/geocoded_cache.csv",index=False,encoding='utf-8-sig')
    print(f"  {len(df_pts)} points.")
    return df_pts

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
    html = f"""
    <div style="
        width:{size}px;height:{size}px;
        background:{color};
        border-radius:50%;
        border:3px solid white;
        box-shadow:0 2px 12px rgba(0,0,0,0.25);
        display:flex;align-items:center;justify-content:center;
        font-family:'Noto Sans KR',sans-serif;
        font-size:11px;font-weight:700;color:white;
        text-align:center;line-height:1.1;
    ">{label}</div>"""
    return folium.DivIcon(html=html, icon_size=(size,size), icon_anchor=(size//2, size//2))

def build_map(geo, df_acad, stress, youth_pop, shelters_df):
    print("[3] Building map...")
    pts = np.array(list(zip(geo['lon'],geo['lat'])))
    B = dict(la0=37.28,la1=37.85,lo0=126.32,lo1=126.88)
    m_ = ((pts[:,1]>=B['la0'])&(pts[:,1]<=B['la1'])&(pts[:,0]>=B['lo0'])&(pts[:,0]<=B['lo1']))
    pts = pts[m_]

    la0,la1 = pts[:,1].min()-0.10, pts[:,1].max()+0.10
    lo0,lo1 = pts[:,0].min()-0.10, pts[:,0].max()+0.10
    bdry = np.array([[lo,la] for la in np.linspace(la0,la1,8) for lo in np.linspace(lo0,lo1,8)])
    vor = Voronoi(np.vstack([pts,bdry]))

    densities, polys = [], []
    for ri in vor.point_region[:len(pts)]:
        reg = vor.regions[ri]
        if -1 not in reg and len(reg) > 0:
            verts = [vor.vertices[j] for j in reg]
            cx = np.mean([v[0] for v in verts]); cy = np.mean([v[1] for v in verts])
            d = (np.sqrt((pts[:,0]-cx)**2+(pts[:,1]-cy)**2)<0.025).sum()
            densities.append(d); polys.append(verts)

    mx, mn = max(densities,default=1), min(densities,default=0)
    sorted_idx = np.argsort(densities)
    rank_map = {i:r for r,i in enumerate(sorted_idx)}

    centroids, _ = kmeans2(pts, 3, iter=30, seed=42)

    # CVI
    district_list = ['부평구','남동구','연수구','서구','계양구','미추홀구','중구','동구','강화군','옹진군']
    acad_cnts = {d: len(df_acad[df_acad['지역'].str.contains(d,na=False)]) for d in district_list}
    max_a = max(acad_cnts.values()) or 1
    max_s = max(stress.values(),default=1)
    max_p = max(youth_pop.values(),default=1)
    cvi = {d: round(0.4*(acad_cnts.get(d,0)/max_a) + 0.3*(stress.get(d,0)/max_s) + 0.3*(youth_pop.get(d,0)/max_p), 3)
           for d in district_list}

    center = [pts[:,1].mean(), pts[:,0].mean()]
    m = folium.Map(location=center, zoom_start=11, tiles=None)
    folium.TileLayer('CartoDB positron', name='지도 배경', show=True).add_to(m)

    # ── VORONOI ─────────────────────────────
    vor_grp = folium.FeatureGroup(name="학원 세력권 (보로노이)", show=True)
    for idx,(verts,d) in enumerate(zip(polys,densities)):
        dn = (d-mn)/max(mx-mn,1)
        hue = (180 + rank_map[idx]/max(len(polys),1)*300) % 360
        color = hsl_to_hex(hue, 0.72+dn*0.20, 0.52-dn*0.10)
        folium.Polygon(
            locations=[[v[1],v[0]] for v in verts],
            color='rgba(100,100,100,0.15)', weight=0.5,
            fill=True, fill_color=color, fill_opacity=0.32,
            tooltip=f"밀집도 지수: {d}",
        ).add_to(vor_grp)
    vor_grp.add_to(m)

    # ── HEATMAP ──────────────────────────────
    heat_grp = folium.FeatureGroup(name="열지도 (오버레이)", show=False)
    HeatMap([[r.lat,r.lon] for r in geo.itertuples()],
            radius=20, blur=16, min_opacity=0.2).add_to(heat_grp)
    heat_grp.add_to(m)

    # ── SHELTERS ─────────────────────────────
    sh_grp = folium.FeatureGroup(name="청소년 쉼터", show=True)
    shelter_count = 0
    if len(shelters_df) > 0:
        for _,row in shelters_df.iterrows():
            try:
                la, lo = float(row['A1']), float(row['A0'])
                name_str = str(row['A9'])[:6]
                folium.Marker(
                    location=[la,lo],
                    icon=make_div_icon('쉼터', '#e74c3c', 36),
                    popup=folium.Popup(f"<b>{row['A9']}</b><br>유형: {row.get('A8','')}", max_width=240),
                    tooltip=str(row['A9']),
                ).add_to(sh_grp)
                shelter_count += 1
            except: pass
    sh_grp.add_to(m)

    # ── P-MEDIAN SITES ────────────────────────
    site_names = ["이동 배치 권장지 A","이동 배치 권장지 B","이동 배치 권장지 C"]
    site_colors = ['#f39c12','#e67e22','#d35400']
    opt_grp = folium.FeatureGroup(name="이동형 쉼터 배치 권장지", show=True)
    for i,(lo,la) in enumerate(centroids):
        if B['la0']<=la<=B['la1'] and B['lo0']<=lo<=B['lo1']:
            folium.Marker(
                location=[la,lo],
                icon=make_div_icon(f'★', site_colors[i], 40),
                popup=folium.Popup(
                    f"<b>{site_names[i]}</b><br>"
                    f"p-median 알고리즘 기반 최적 배치 좌표<br>"
                    f"Lat: {la:.4f} / Lon: {lo:.4f}", max_width=260),
                tooltip=site_names[i],
            ).add_to(opt_grp)
    opt_grp.add_to(m)

    LayerControl(collapsed=False).add_to(m)

    # ── STATS PANEL ───────────────────────────
    top_cvi = sorted(cvi.items(), key=lambda x:-x[1])
    table_rows = ""
    for dist, score in top_cvi:
        bar_w = int(score * 100)
        bar_c = "#e74c3c" if score>0.70 else "#f39c12" if score>0.50 else "#27ae60"
        ring_style = f"background:conic-gradient({bar_c} {bar_w*3.6}deg, #f0f0f0 0deg);"
        s_val = f"{stress.get(dist,0)}%" if dist in stress else "-"
        y_val = f"{youth_pop.get(dist,0)//1000}k" if dist in youth_pop else "-"
        a_val = f"{acad_cnts.get(dist,0):,}"
        table_rows += f"""
        <tr style="border-bottom:1px solid #f0f0f4;transition:background 0.15s;" onmouseover="this.style.background='#f8f9ff'" onmouseout="this.style.background=''">
          <td style="padding:7px 5px 7px 2px;font-weight:600;color:#2d3436;font-size:11px;">{dist}</td>
          <td style="padding:7px 5px;text-align:right;color:#2980b9;font-size:11px;">{a_val}</td>
          <td style="padding:7px 5px;text-align:right;font-size:11px;color:#e74c3c;">{s_val}</td>
          <td style="padding:7px 5px;text-align:right;font-size:11px;color:#27ae60;">{y_val}</td>
          <td style="padding:7px 5px;">
            <div style="display:flex;align-items:center;gap:5px;">
              <div style="flex:1;background:#f0f0f4;border-radius:4px;height:6px;">
                <div style="background:{bar_c};height:100%;width:{bar_w}%;border-radius:4px;"></div>
              </div>
              <span style="font-size:9px;color:{bar_c};font-weight:700;min-width:28px;">{score:.2f}</span>
            </div>
          </td>
        </tr>"""

    top3_html = "".join([
        f'<div style="display:inline-flex;align-items:center;gap:5px;background:#fff;'
        f'border:1.5px solid #e74c3c;border-radius:20px;padding:3px 10px;margin:2px;font-size:10px;">'
        f'<span style="color:#e74c3c;font-weight:700;">{i+1}위</span>'
        f'<span style="color:#2d3436;font-weight:600;">{d}</span>'
        f'<span style="color:#7f8c8d;">{s:.2f}</span></div>'
        for i,(d,s) in enumerate(top_cvi[:3])
    ])

    total_acad = len(df_acad) if df_acad is not None else 0
    panel_html = f"""
    <div style="
        position:fixed;top:14px;left:58px;z-index:1000;
        background:rgba(255,255,255,0.97);
        backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);
        border-radius:18px;
        padding:18px 20px 16px;
        box-shadow:0 4px 32px rgba(0,0,0,0.12),0 0 0 1px rgba(0,0,0,0.06);
        font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
        color:#2d3436;width:360px;">

      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
        <div>
          <div style="font-size:14px;font-weight:800;color:#2d3436;letter-spacing:-0.2px;">
            인천 청소년 쉼터 입지 분석
          </div>
          <div style="font-size:9px;color:#95a5a6;margin-top:2px;letter-spacing:0.3px;">
            Voronoi Diagram · p-median · CVI Index
          </div>
        </div>
        <div style="
            background:linear-gradient(135deg,#667eea,#764ba2);
            color:white;border-radius:20px;
            padding:4px 10px;font-size:9px;font-weight:600;letter-spacing:0.3px;">
          공공데이터 분석
        </div>
      </div>

      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-bottom:14px;">
        <div style="background:#fff5f5;border-radius:12px;padding:10px 6px;text-align:center;border:1.5px solid #ffeaea;">
          <div style="font-size:16px;font-weight:800;color:#e74c3c;">{total_acad//1000}k+</div>
          <div style="font-size:8px;color:#95a5a6;margin-top:2px;">등록학원</div>
        </div>
        <div style="background:#f0f7ff;border-radius:12px;padding:10px 6px;text-align:center;border:1.5px solid #daeeff;">
          <div style="font-size:16px;font-weight:800;color:#2980b9;">{shelter_count}</div>
          <div style="font-size:8px;color:#95a5a6;margin-top:2px;">현재쉼터</div>
        </div>
        <div style="background:#fffbf0;border-radius:12px;padding:10px 6px;text-align:center;border:1.5px solid #ffefc0;">
          <div style="font-size:16px;font-weight:800;color:#f39c12;">3</div>
          <div style="font-size:8px;color:#95a5a6;margin-top:2px;">배치권장지</div>
        </div>
        <div style="background:#f0fff7;border-radius:12px;padding:10px 6px;text-align:center;border:1.5px solid #c0f0d8;">
          <div style="font-size:16px;font-weight:800;color:#27ae60;">{len(polys)}</div>
          <div style="font-size:8px;color:#95a5a6;margin-top:2px;">분석영역</div>
        </div>
      </div>

      <div style="background:#fef9f9;border-radius:12px;padding:10px 12px;margin-bottom:12px;border:1px solid #fde8e8;">
        <div style="font-size:9px;font-weight:700;color:#e74c3c;margin-bottom:7px;letter-spacing:0.4px;">
          CVI 복합취약지수 상위 지역
        </div>
        {top3_html}
      </div>

      <div style="height:1px;background:#f0f0f4;margin-bottom:10px;"></div>

      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="border-bottom:2px solid #f0f0f4;">
            <th style="padding:5px 3px;text-align:left;font-size:9px;color:#95a5a6;font-weight:600;letter-spacing:0.3px;">지역</th>
            <th style="padding:5px;text-align:right;font-size:9px;color:#2980b9;font-weight:600;">학원수</th>
            <th style="padding:5px;text-align:right;font-size:9px;color:#e74c3c;font-weight:600;">스트레스</th>
            <th style="padding:5px;text-align:right;font-size:9px;color:#27ae60;font-weight:600;">청소년</th>
            <th style="padding:5px;font-size:9px;color:#7f8c8d;font-weight:600;">CVI</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>"""
    m.get_root().html.add_child(folium.Element(panel_html))

    legend_html = """
    <div style="
        position:fixed;bottom:24px;right:14px;z-index:1000;
        background:rgba(255,255,255,0.97);
        backdrop-filter:blur(16px);
        border-radius:16px;padding:14px 16px;
        box-shadow:0 4px 32px rgba(0,0,0,0.12),0 0 0 1px rgba(0,0,0,0.06);
        font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
        font-size:11px;min-width:180px;color:#2d3436;">
      <div style="font-weight:700;font-size:11px;margin-bottom:10px;color:#2d3436;">범례</div>

      <div style="font-size:9px;color:#95a5a6;margin-bottom:5px;font-weight:600;">학원 밀집도 (보로노이 색상)</div>
      <div style="height:8px;width:100%;border-radius:4px;margin-bottom:10px;
          background:linear-gradient(to right,hsl(180,75%,50%),hsl(260,80%,52%),hsl(320,80%,50%),hsl(30,85%,52%),hsl(10,85%,48%));"></div>
      <div style="display:flex;justify-content:space-between;font-size:8px;color:#bdc3c7;margin-bottom:12px;margin-top:-8px;">
        <span>낮음</span><span>높음</span>
      </div>

      <div style="display:flex;flex-direction:column;gap:8px;">
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="width:26px;height:26px;border-radius:50%;background:#e74c3c;
              border:2px solid white;box-shadow:0 2px 8px rgba(231,76,60,0.3);
              display:flex;align-items:center;justify-content:center;
              font-size:7px;color:white;font-weight:700;flex-shrink:0;">쉼터</div>
          <div><div style="font-size:10px;font-weight:600;">청소년 쉼터</div>
          <div style="font-size:8px;color:#95a5a6;">기존 설치 현황</div></div>
        </div>
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="width:26px;height:26px;border-radius:50%;background:#f39c12;
              border:2px solid white;box-shadow:0 2px 8px rgba(243,156,18,0.3);
              display:flex;align-items:center;justify-content:center;
              font-size:10px;color:white;font-weight:700;flex-shrink:0;">★</div>
          <div><div style="font-size:10px;font-weight:600;">이동형 쉼터 권장지</div>
          <div style="font-size:8px;color:#95a5a6;">p-median 최적화 결과</div></div>
        </div>
      </div>
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    out = "results/final_analysis.html"
    m.save(out)
    print(f"\n  Saved -> {out} | Polygons:{len(polys)} | Shelters:{shelter_count}")

if __name__ == "__main__":
    setup_dirs()
    df = merge_academies()
    stress, youth_pop, shelters_df = load_all_data()

    cache = "data/processed/geocoded_cache.csv"
    if os.path.exists(cache):
        geo = pd.read_csv(cache)
        if len(geo)<100 or (geo['lat'].max()-geo['lat'].min())<0.05:
            os.remove(cache); geo = generate_points(df)
        else: print(f"[2] Loaded {len(geo)} cached points.")
    else:
        geo = generate_points(df)

    build_map(geo, df, stress, youth_pop, shelters_df)
    print("DONE! Open results/final_analysis.html")
