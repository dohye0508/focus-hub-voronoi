# 🚀 청소년 쉼터 접근성 조회 및 최적 입지 선정 서비스 (V2)

**제8회 한국코드페어 해커톤 예선 출품작**

본 프로젝트는 신뢰할 수 있는 AI와 데이터를 활용하여, 복지 사각지대에 놓인 청소년들을 위한 **"이동형 청소년 쉼터 최적 입지(p-median) 추천 및 커버리지 분석 웹앱"**입니다.

👉 **[웹 서비스 바로가기 (Live Demo)](https://dohye0508.github.io/focus-hub-voronoi/)**

---

## 🌟 V2 주요 개선사항 (초기 작품 대비)

기존 Python 기반의 복잡한 서버 아키텍처(V1)의 한계를 극복하고, 누구나 언제 어디서든 접속하여 조작해볼 수 있는 **100% 브라우저 기반 정적 웹앱(PWA)**으로 재탄생했습니다.

1. **서버 없는 순수 웹앱 (Serverless Web App)**
   - 백엔드 서버 없이 GitHub Pages를 통해 배포됩니다.
   - 복잡한 Voronoi 폴리곤 및 CVI 연산은 사전에 `export_data.py`로 처리하여 가벼운 GeoJSON 데이터(`cells.json`, `shelters.json`)로 최적화했습니다.

2. **실시간 브라우저 최적화 엔진 (Real-time P-median & K-means)**
   - JavaScript로 경량화된 최적화 알고리즘이 탑재되었습니다.
   - 사용자가 **추가 쉼터 개수(P)**와 **효율-형평성 균형(λ)** 슬라이더를 조작하는 즉시, 실시간으로 최적 입지를 재계산하고 지도에 렌더링합니다.

3. **고급 시각적 분석 (Visual Analytics) & 모던 UI**
   - **다크 글래스모피즘(Glassmorphism) 테마**: 사이버네틱하고 전문적인 분석 느낌을 주는 모던 UI 패널 (좌측 배치로 시야 확보).
   - **할당선(Spider Web) 및 커버리지 서클(2km)**: 추천된 최적 쉼터가 어느 지역을 커버하는지 시각적으로 증명하는 라인과 반경을 제공합니다.
   - **복합취약지수(CVI) 히트맵**: 지역별 취약도를 색상으로 명확히 표현합니다.

4. **사용자 친화적 기능 추가**
   - **GPS 위치 기반 분석**: 원클릭으로 내 위치 주변의 쉼터 접근성과 소속된 지역의 취약도를 조회합니다.
   - **주소 검색 기능**: 특정 지역이나 주소를 검색하여 해당 구역의 쉼터 접근성을 즉시 파악할 수 있습니다.

---

## 🛠 기술 스택

- **Frontend**: HTML5, CSS3, Vanilla JavaScript (ES6+), Leaflet.js
- **Data Preprocessing**: Python 3, GeoPandas, Scikit-learn
- **Hosting**: GitHub Pages

## 📂 디렉토리 구조

```
📦 focus-hub-voronoi
 ┣ 📂 css/              # UI 스타일 (다크모드, 글래스모피즘)
 ┣ 📂 js/               # 애플리케이션 로직 (지도, 최적화, 위치/검색 모듈)
 ┣ 📂 public/data/      # 사전 처리된 GeoJSON 파일들
 ┣ 📂 scripts/          # 데이터 전처리 및 모델 학습 Python 스크립트
 ┣ 📂 results/          # 기획안 및 분석 결과 문서
 ┣ 📜 index.html        # 메인 웹 페이지
 ┗ 📜 README.md         # 프로젝트 설명
```

## 🚀 로컬 실행 방법

1. 저장소를 클론합니다.
   ```bash
   git clone https://github.com/dohye0508/focus-hub-voronoi.git
   cd focus-hub-voronoi
   ```
2. 로컬 웹 서버를 실행합니다.
   ```bash
   python -m http.server 8000
   ```
3. 브라우저에서 `http://localhost:8000` 으로 접속합니다.
