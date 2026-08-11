import os
import sys
import json
import numpy as np
import pandas as pd
from scipy.spatial import Voronoi
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import MinMaxScaler

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from main import load_academies, load_stress, load_population, load_shelters, get_coords
except ImportError:
    print("Error: Could not import data loaders from main.py")
    sys.exit(1)

def export_data():
    print("=== 데이터 로딩 ===")
    acad = load_academies()
    stress = load_stress()
    pop = load_population()
    shelters = load_shelters()
    coords = get_coords()

    # 1. 머신러닝 데이터셋 준비 (CVI 학습)
    data = []
    has_shelter = {reg: 0 for reg in coords}
    
    shelters_geojson = {"type": "FeatureCollection", "features": []}
    
    if len(shelters) > 0:
        for _, row in shelters.iterrows():
            try:
                geom = row.geometry
                if geom is None or geom.is_empty: continue
                lo, la = geom.x, geom.y
                if not (124 < lo < 132 and 33 < la < 39): continue
                
                # closest region for label
                min_dist = float('inf')
                closest_reg = None
                for reg, (r_la, r_lo) in coords.items():
                    dist = (r_la - la)**2 + (r_lo - lo)**2
                    if dist < min_dist:
                        min_dist = dist
                        closest_reg = reg
                if closest_reg:
                    has_shelter[closest_reg] = 1
                
                # Add to shelters GeoJSON
                shelters_geojson["features"].append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lo, la]},
                    "properties": {
                        "name": str(row.get('A9', '쉼터')),
                        "address": str(row.get('A10', '')),
                        "phone": str(row.get('A11', ''))
                    }
                })
            except Exception as e:
                print(f"Error parsing shelter: {e}")
                
    for reg in coords:
        data.append({
            'region': reg,
            'academy': acad.get(reg, 0),
            'stress': stress.get(reg, 0),
            'population': pop.get(reg, 0),
            'has_shelter': has_shelter[reg]
        })
        
    df = pd.DataFrame(data)
    scaler = MinMaxScaler()
    X_raw = df[['academy', 'stress', 'population']]
    X_norm = scaler.fit_transform(X_raw)
    
    X = X_norm
    y = df['has_shelter']
    
    # 2. 로지스틱 회귀 모델 학습 및 CVI 계산
    model = LogisticRegression(class_weight='balanced', random_state=42)
    model.fit(X, y)
    df['cvi'] = model.predict_proba(X)[:, 1] # 확률값을 CVI로 사용
    
    cvi_dict = dict(zip(df['region'], df['cvi']))
    pop_dict = dict(zip(df['region'], df['population']))
    acad_dict = dict(zip(df['region'], df['academy']))
    
    # 3. 보로노이 다이어그램 생성 (main.py 로직 복제)
    seeds = []
    seed_regs = []
    for reg, (la, lo) in coords.items():
        seeds.append((lo + np.random.uniform(-0.001, 0.001),
                       la + np.random.uniform(-0.001, 0.001)))
        seed_regs.append(reg)
    seeds = np.array(seeds)

    KOR_LAT = (33.0, 38.7)
    KOR_LON = (124.5, 130.0)
    bdry = []
    for la in np.linspace(KOR_LAT[0]-1, KOR_LAT[1]+1, 40):
        bdry.append([KOR_LON[0]-1, la])
        bdry.append([KOR_LON[1]+1, la])
    for lo in np.linspace(KOR_LON[0]-1, KOR_LON[1]+1, 40):
        bdry.append([lo, KOR_LAT[0]-1])
        bdry.append([lo, KOR_LAT[1]+1])
    bdry = np.array(bdry)

    all_pts = np.vstack([seeds, bdry])
    vor = Voronoi(all_pts)
    
    cells_geojson = {"type": "FeatureCollection", "features": []}
    
    for i, ri in enumerate(vor.point_region[:len(seeds)]):
        region_idx = vor.regions[ri]
        if -1 in region_idx or len(region_idx) == 0:
            continue
        verts = [vor.vertices[j] for j in region_idx]
        
        cx = np.mean([v[0] for v in verts])
        cy = np.mean([v[1] for v in verts])
        if not (KOR_LON[0] <= cx <= KOR_LON[1] and KOR_LAT[0] <= cy <= KOR_LAT[1]):
            continue
            
        reg = seed_regs[i]
        cvi = cvi_dict.get(reg, 0)
        p = pop_dict.get(reg, 0)
        a = acad_dict.get(reg, 0)
        
        cells_geojson["features"].append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[float(v[0]), float(v[1])] for v in verts]]
            },
            "properties": {
                "region": reg,
                "cvi": float(cvi),
                "population": int(p),
                "academy": int(a),
                "centroid": [float(cx), float(cy)]
            }
        })
        
    os.makedirs('public/data', exist_ok=True)
    
    with open('public/data/cells.json', 'w', encoding='utf-8') as f:
        json.dump(cells_geojson, f, ensure_ascii=False)
        
    with open('public/data/shelters.json', 'w', encoding='utf-8') as f:
        json.dump(shelters_geojson, f, ensure_ascii=False)
        
    print(f"[DONE] Saved cells.json (N={len(cells_geojson['features'])}) and shelters.json (N={len(shelters_geojson['features'])})")

if __name__ == "__main__":
    export_data()
