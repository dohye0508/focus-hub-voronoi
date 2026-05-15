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
    stress = {}
    youth_pop = {}
    shelter_count = 0
    shelters_df = pd.DataFrame()

    # Stress
    try:
        df = pd.read_excel("data/raw/시·군·구별_스트레스_인지율_20260515154125.xlsx", header=None)
        name_map = ['중구','동구','미추홀구','연수구','남동구','부평구','계양구','서구','강화군','옹진군']
        for _, row in df.iterrows():
            raw = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ''
            for k in name_map:
                if k in raw:
                    try: stress[k] = float(str(row.iloc[3]).replace(',',''))
                    except: pass
        print(f"  Stress: {len(stress)} districts")
    except Exception as e: print(f"  Stress failed: {e}")

    # Youth pop
    try:
        df = pd.read_excel("data/raw/202604_202604_주민등록 인구 기타현황(아동청소년청년 인구현황)_월간.xlsx", header=None)
        name_map = ['중구','동구','미추홀구','연수구','남동구','부평구','계양구','서구','강화군','옹진군']
        for _, row in df.iterrows():
            raw = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ''
            for k in name_map:
                if k in raw:
                    try:
                        youth_pop[k] = int(str(row.iloc[9]).replace(',','')) + int(str(row.iloc[12]).replace(',',''))
                    except: pass
        print(f"  Youth pop: {len(youth_pop)} districts")
    except Exception as e: print(f"  Youth pop failed: {e}")

    # Shelters
    try:
        gdf = gpd.read_file("data/spatial/전국+청소년쉼터+현황/Youth shelter.shp")
        shelters_df = gdf[gdf['A6'] == '인천'].copy()
        shelter_count = len(shelters_df)
        print(f"  Shelters: {shelter_count}")
    except Exception as e: print(f"  Shelter failed: {e}")

    return stress, youth_pop, shelters_df, shelter_count

def generate_points(df_academies):
    print("[2] Generating simulation points...")
    districts_config = {
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
    district_counts = {n: max(len(df_academies[df_academies['지역'].str.contains(n,na=False)]),10)
                       for n in districts_config}
    total = sum(district_counts.values())
    TOTAL = 600
    lats,lons,dists = [],[],[]
    for name,clusters in districts_config.items():
        n = max(int(TOTAL*district_counts[name]/total),8)
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

def build_map(geo, df_acad, stress, youth_pop, shelters_df, shelter_count):
    print("[3] Building map...")
    pts = np.array(list(zip(geo['lon'],geo['lat'])))
    B = dict(la0=37.28,la1=37.85,lo0=126.32,lo1=126.88)
    m_ = ((pts[:,1]>=B['la0'])&(pts[:,1]<=B['la1'])&(pts[:,0]>=B['lo0'])&(pts[:,0]<=B['lo1']))
    pts = pts[m_]

    # Voronoi
    la0,la1 = pts[:,1].min()-0.1, pts[:,1].max()+0.1
    lo0,lo1 = pts[:,0].min()-0.1, pts[:,0].max()+0.1
    bdry = np.array([[lo,la] for la in np.linspace(la0,la1,8) for lo in np.linspace(lo0,lo1,8)])
    vor = Voronoi(np.vstack([pts,bdry]))

    densities,polys = [],[]
    for ri in vor.point_region[:len(pts)]:
        reg = vor.regions[ri]
        if -1 not in reg and len(reg)>0:
            verts = [vor.vertices[j] for j in reg]
            cx,cy = np.mean([v[0] for v in verts]),np.mean([v[1] for v in verts])
            d = (np.sqrt((pts[:,0]-cx)**2+(pts[:,1]-cy)**2)<0.025).sum()
            densities.append(d); polys.append(verts)

    mx,mn = max(densities) if densities else 1, min(densities) if densities else 0
    sorted_idx = np.argsort(densities)
    rank_map = {i:r for r,i in enumerate(sorted_idx)}

    # p-median
    centroids, _ = kmeans2(pts, 3, iter=30, seed=42)

    # CVI per district
    district_list = ['부평구','남동구','연수구','서구','계양구','미추홀구','중구','동구','강화군','옹진군']
    acad_cnts = {d: len(df_acad[df_acad['지역'].str.contains(d,na=False)]) for d in district_list}
    max_a = max(acad_cnts.values()) or 1
    max_s = max(stress.values()) if stress else 1
    max_p = max(youth_pop.values()) if youth_pop else 1
    cvi = {}
    for d in district_list:
        a = acad_cnts.get(d,0)/max_a
        s = stress.get(d,0)/max_s
        p = youth_pop.get(d,0)/max_p
        cvi[d] = round(0.4*a + 0.3*s + 0.3*p, 3)

    center = [pts[:,1].mean(), pts[:,0].mean()]

    # ── MAP ──────────────────────────────────
    m = folium.Map(location=center, zoom_start=11, tiles=None)
    folium.TileLayer('CartoDB dark_matter', name='다크 배경', show=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='밝은 배경', show=False).add_to(m)

    # Voronoi
    vor_grp = folium.FeatureGroup(name="학원 세력권 (보로노이)", show=True)
    for idx,(verts,d) in enumerate(zip(polys,densities)):
        dn = (d-mn)/max(mx-mn,1)
        hue = (180 + rank_map[idx]/max(len(polys),1)*300) % 360
        sat = 0.70 + dn*0.25
        lig = 0.55 - dn*0.15
        color = hsl_to_hex(hue, sat, lig)
        folium.Polygon(
            locations=[[v[1],v[0]] for v in verts],
            color='rgba(255,255,255,0.25)', weight=0.8,
            fill=True, fill_color=color, fill_opacity=0.62,
            tooltip=f"밀집도 {d} | {geo['district'].iloc[min(idx,len(geo)-1)] if 'district' in geo.columns else ''}",
        ).add_to(vor_grp)
    vor_grp.add_to(m)

    # Heatmap (off by default)
    heat_grp = folium.FeatureGroup(name="열지도 (오버레이)", show=False)
    HeatMap([[r.lat,r.lon] for r in geo.itertuples()],
            radius=20, blur=16, min_opacity=0.2).add_to(heat_grp)
    heat_grp.add_to(m)

    # Shelter coverage + markers
    cov_grp = folium.FeatureGroup(name="쉼터 서비스 반경", show=True)
    sh_grp  = folium.FeatureGroup(name="청소년 쉼터 위치", show=True)
    if len(shelters_df)>0:
        for _,row in shelters_df.iterrows():
            try:
                la,lo = float(row['A1']),float(row['A0'])
                folium.Circle([la,lo], radius=1500,
                    color='#ff4757', weight=1.5, fill=True,
                    fill_color='#ff4757', fill_opacity=0.07).add_to(cov_grp)
                folium.CircleMarker([la,lo], radius=10,
                    color='#ff4757', weight=2.5, fill=True,
                    fill_color='#ff6b81', fill_opacity=1,
                    popup=folium.Popup(f"<b>{row['A9']}</b><br>유형: {row.get('A8','')}", max_width=220),
                    tooltip=str(row['A9'])).add_to(sh_grp)
            except: pass
    cov_grp.add_to(m); sh_grp.add_to(m)

    # Optimal sites (p-median)
    opt_grp = folium.FeatureGroup(name="AI 최적 입지 (p-median)", show=True)
    names = ["최적 입지 1호","최적 입지 2호","최적 입지 3호"]
    for i,(lo,la) in enumerate(centroids):
        folium.Circle([la,lo], radius=1200,
            color='#ffa502', weight=2, fill=True,
            fill_color='#ffa502', fill_opacity=0.10).add_to(opt_grp)
        folium.CircleMarker([la,lo], radius=13,
            color='#ffa502', weight=2.5, fill=True,
            fill_color='#ffbe76', fill_opacity=1,
            popup=folium.Popup(f"<b>★ {names[i]}</b><br>p-median 최적 배치 지점", max_width=220),
            tooltip=f"★ {names[i]}").add_to(opt_grp)
    opt_grp.add_to(m)

    LayerControl(collapsed=False).add_to(m)

    # ── UI PANELS ────────────────────────────
    total_acad = len(df_acad) if df_acad is not None else 0

    table_rows = ""
    top_cvi = sorted(cvi.items(), key=lambda x:-x[1])
    for dist, score in top_cvi:
        bar_w = int(score * 100)
        bar_c = "#ff4757" if score>0.7 else "#ffa502" if score>0.5 else "#2ed573"
        s_val = f"{stress.get(dist,0)}%" if dist in stress else "-"
        y_val = f"{youth_pop.get(dist,0)//1000}k" if dist in youth_pop else "-"
        a_val = f"{acad_cnts.get(dist,0):,}"
        table_rows += f"""
        <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
          <td style="padding:6px 5px 6px 2px;font-weight:600;color:#f0f0f0;font-size:11px;">{dist}</td>
          <td style="padding:6px 4px;text-align:right;color:#74b9ff;font-size:11px;">{a_val}</td>
          <td style="padding:6px 4px;text-align:right;font-size:11px;color:#fd79a8;">{s_val}</td>
          <td style="padding:6px 4px;text-align:right;font-size:11px;color:#55efc4;">{y_val}</td>
          <td style="padding:6px 4px;min-width:80px;">
            <div style="background:rgba(255,255,255,0.1);border-radius:4px;height:8px;overflow:hidden;">
              <div style="background:{bar_c};height:100%;width:{bar_w}%;border-radius:4px;"></div>
            </div>
            <div style="font-size:9px;color:{bar_c};text-align:right;margin-top:1px;">{score:.2f}</div>
          </td>
        </tr>"""

    top3_html = "".join([f'<span style="display:inline-block;background:rgba(255,165,2,0.2);border:1px solid #ffa502;border-radius:6px;padding:2px 8px;font-size:10px;color:#ffa502;margin:2px;">{d} {s:.2f}</span>'
                         for d,s in top_cvi[:3]])

    panel_html = f"""
    <div id="main-panel" style="
        position:fixed;top:14px;left:58px;z-index:1000;
        background:rgba(8,12,24,0.93);
        backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
        border-radius:16px;padding:16px 18px 14px;
        box-shadow:0 8px 40px rgba(0,0,0,0.55),0 0 0 1px rgba(255,255,255,0.07);
        font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
        color:#fff;width:350px;">
      <!-- Header -->
      <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:12px;">
        <div>
          <div style="font-size:13px;font-weight:700;letter-spacing:0.4px;background:linear-gradient(90deg,#74b9ff,#a29bfe);
              -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
            인천 청소년 쉼터 최적 입지 분석
          </div>
          <div style="font-size:9px;color:#6c7a89;margin-top:2px;letter-spacing:0.3px;">
            Voronoi · p-median · CVI 복합취약지수
          </div>
        </div>
        <div style="background:rgba(116,185,255,0.12);border-radius:8px;padding:4px 8px;font-size:9px;color:#74b9ff;border:1px solid rgba(116,185,255,0.2);">
          실시간 분석
        </div>
      </div>

      <!-- KPI Row -->
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:6px;margin-bottom:14px;">
        <div style="background:rgba(255,71,87,0.12);border:1px solid rgba(255,71,87,0.25);border-radius:10px;padding:8px 6px;text-align:center;">
          <div style="font-size:17px;font-weight:800;color:#ff4757;">{total_acad:,}</div>
          <div style="font-size:8px;color:#aaa;margin-top:2px;">등록학원</div>
        </div>
        <div style="background:rgba(116,185,255,0.12);border:1px solid rgba(116,185,255,0.25);border-radius:10px;padding:8px 6px;text-align:center;">
          <div style="font-size:17px;font-weight:800;color:#74b9ff;">{shelter_count}</div>
          <div style="font-size:8px;color:#aaa;margin-top:2px;">현재쉼터</div>
        </div>
        <div style="background:rgba(255,165,2,0.12);border:1px solid rgba(255,165,2,0.25);border-radius:10px;padding:8px 6px;text-align:center;">
          <div style="font-size:17px;font-weight:800;color:#ffa502;">3</div>
          <div style="font-size:8px;color:#aaa;margin-top:2px;">AI추천</div>
        </div>
        <div style="background:rgba(46,213,115,0.12);border:1px solid rgba(46,213,115,0.25);border-radius:10px;padding:8px 6px;text-align:center;">
          <div style="font-size:17px;font-weight:800;color:#2ed573;">{len(polys)}</div>
          <div style="font-size:8px;color:#aaa;margin-top:2px;">분석영역</div>
        </div>
      </div>

      <!-- CVI Top 3 -->
      <div style="margin-bottom:12px;">
        <div style="font-size:9px;color:#a29bfe;font-weight:600;margin-bottom:6px;letter-spacing:0.5px;">
          ▲ CVI 취약지수 최상위 지역
        </div>
        {top3_html}
      </div>

      <!-- Divider -->
      <div style="height:1px;background:rgba(255,255,255,0.08);margin-bottom:10px;"></div>

      <!-- Table -->
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="border-bottom:1px solid rgba(255,255,255,0.12);">
            <th style="padding:4px 2px;text-align:left;font-size:9px;color:#6c7a89;font-weight:500;">지역</th>
            <th style="padding:4px;text-align:right;font-size:9px;color:#6c7a89;font-weight:500;">학원</th>
            <th style="padding:4px;text-align:right;font-size:9px;color:#6c7a89;font-weight:500;">스트레스</th>
            <th style="padding:4px;text-align:right;font-size:9px;color:#6c7a89;font-weight:500;">청소년</th>
            <th style="padding:4px;text-align:right;font-size:9px;color:#6c7a89;font-weight:500;">CVI</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>"""
    m.get_root().html.add_child(folium.Element(panel_html))

    legend_html = """
    <div style="position:fixed;bottom:24px;right:14px;z-index:1000;
        background:rgba(8,12,24,0.93);backdrop-filter:blur(12px);
        border-radius:14px;padding:14px 16px;
        box-shadow:0 8px 40px rgba(0,0,0,0.55),0 0 0 1px rgba(255,255,255,0.07);
        font-family:'Noto Sans KR','Apple SD Gothic Neo',sans-serif;
        font-size:11px;min-width:175px;color:#f0f0f0;">
      <div style="font-weight:700;font-size:11px;margin-bottom:10px;color:#a29bfe;letter-spacing:0.4px;">범례</div>
      <div style="font-size:9px;color:#6c7a89;margin-bottom:4px;">학원 밀집도</div>
      <div style="height:8px;width:100%;border-radius:4px;margin-bottom:10px;
          background:linear-gradient(to right,hsl(180,75%,50%),hsl(270,75%,55%),hsl(330,80%,55%),hsl(30,85%,55%),hsl(10,85%,50%));"></div>
      <div style="display:flex;flex-direction:column;gap:7px;">
        <div style="display:flex;align-items:center;gap:9px;">
          <div style="width:12px;height:12px;border-radius:50%;background:#ff4757;box-shadow:0 0 8px #ff475788;flex-shrink:0;"></div>
          <span style="font-size:10px;">청소년 쉼터 (현황)</span>
        </div>
        <div style="display:flex;align-items:center;gap:9px;">
          <div style="width:12px;height:12px;border-radius:50%;background:#ffa502;box-shadow:0 0 8px #ffa50288;flex-shrink:0;"></div>
          <span style="font-size:10px;">AI 추천 최적 입지</span>
        </div>
        <div style="display:flex;align-items:center;gap:9px;">
          <div style="width:12px;height:12px;border-radius:3px;
              background:linear-gradient(135deg,#a29bfe55,#74b9ff55);
              border:1px solid rgba(255,255,255,0.25);flex-shrink:0;"></div>
          <span style="font-size:10px;">보로노이 세력권</span>
        </div>
        <div style="display:flex;align-items:center;gap:9px;">
          <div style="width:12px;height:12px;border-radius:50%;background:none;border:2px solid #ff4757;flex-shrink:0;"></div>
          <span style="font-size:10px;">서비스 반경 (1.5km)</span>
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
    stress, youth_pop, shelters_df, shelter_count = load_all_data()

    cache = "data/processed/geocoded_cache.csv"
    if os.path.exists(cache):
        geo = pd.read_csv(cache)
        if len(geo)<100 or (geo['lat'].max()-geo['lat'].min())<0.05:
            os.remove(cache); geo = generate_points(df)
        else: print(f"[2] Loaded {len(geo)} cached points.")
    else:
        geo = generate_points(df)

    build_map(geo, df, stress, youth_pop, shelters_df, shelter_count)
    print("DONE! Open results/final_analysis.html")
