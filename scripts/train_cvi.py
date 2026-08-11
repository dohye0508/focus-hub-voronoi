import os
import sys
import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, confusion_matrix

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from main import load_academies, load_stress, load_population, load_shelters, get_coords
except ImportError:
    print("Error: Could not import data loaders from main.py")
    sys.exit(1)

def main():
    print("=== 데이터 로딩 ===")
    acad = load_academies()
    stress = load_stress()
    pop = load_population()
    shelters = load_shelters()
    coords = get_coords()

    print("\n=== 1. 셀 단위 집계 및 정규화 ===")
    data = []
    
    has_shelter = {reg: 0 for reg in coords}
    if len(shelters) > 0:
        for _, row in shelters.iterrows():
            try:
                geom = row.geometry
                if geom is None or geom.is_empty: continue
                lo, la = geom.x, geom.y
                if not (124 < lo < 132 and 33 < la < 39): continue
                
                min_dist = float('inf')
                closest_reg = None
                for reg, (r_la, r_lo) in coords.items():
                    dist = (r_la - la)**2 + (r_lo - lo)**2
                    if dist < min_dist:
                        min_dist = dist
                        closest_reg = reg
                if closest_reg:
                    has_shelter[closest_reg] = 1
            except:
                pass
                
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
    df[['A_norm', 'S_norm', 'P_norm']] = X_norm
    
    X = df[['A_norm', 'S_norm', 'P_norm']]
    y = df['has_shelter']
    
    print(f"총 분석 대상 지역: {len(df)}개")
    print(f"쉼터 보유 지역: {y.sum()}개")
    
    print("\n=== 2. 상관행렬 확인 (다중공선성) ===")
    print(X.corr())
    
    print("\n=== 3. 모델 학습 (Logistic Regression) ===")
    model = LogisticRegression(class_weight='balanced', random_state=42)
    model.fit(X, y)
    
    w1, w2, w3 = model.coef_[0]
    b = model.intercept_[0]
    
    print(f"학습된 가중치:")
    print(f"  w1 (학원): {w1:.4f}")
    print(f"  w2 (스트레스): {w2:.4f}")
    print(f"  w3 (인구): {w3:.4f}")
    print(f"  b (절편): {b:.4f}")
    
    print("\n=== 4. 출력 및 증거물 ===")
    sum_w = abs(w1) + abs(w2) + abs(w3)
    p1 = abs(w1) / sum_w * 100
    p2 = abs(w2) / sum_w * 100
    p3 = abs(w3) / sum_w * 100
    
    print("\n[4-1. 계수 비교표]")
    print(f"| 변수 | 우리가 정한 값 | 학습된 값 |")
    print(f"|---|---|---|")
    print(f"| 학원 밀도 | 40.0% | {p1:.1f}% |")
    print(f"| 스트레스 인지율 | 30.0% | {p2:.1f}% |")
    print(f"| 청소년 인구 | 30.0% | {p3:.1f}% |")
    
    y_pred = model.predict(X)
    acc = accuracy_score(y, y_pred)
    prec = precision_score(y, y_pred, zero_division=0)
    rec = recall_score(y, y_pred, zero_division=0)
    cm = confusion_matrix(y, y_pred)
    
    print("\n[검증 지표]")
    print(f"정확도(Accuracy): {acc:.3f}")
    print(f"정밀도(Precision): {prec:.3f}")
    print(f"재현율(Recall): {rec:.3f}")
    print("혼동행렬(Confusion Matrix):")
    print(cm)
    
    df['cvi_prob'] = model.predict_proba(X)[:, 1]
    underserved = df[df['has_shelter'] == 0].sort_values(by='cvi_prob', ascending=False)
    
    print("\n[4-4. 소외 지역 실명 사례 Top 3]")
    print(underserved[['region', 'population', 'cvi_prob']].head(3).to_markdown())
    
    os.makedirs('results', exist_ok=True)
    with open('results/coeffs.json', 'w', encoding='utf-8') as f:
        json.dump({
            'w1': w1, 'w2': w2, 'w3': w3, 'b': b,
            'top3_underserved': underserved['region'].head(3).tolist(),
            'top3_populations': underserved['population'].head(3).tolist(),
            'top3_cvi_prob': underserved['cvi_prob'].head(3).tolist()
        }, f, ensure_ascii=False)
    print("\n[DONE] Saved coefficients to results/coeffs.json")

if __name__ == "__main__":
    main()
