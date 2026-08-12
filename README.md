# Focus-Hub Voronoi: 청소년 이동형 쉼터 실시간 공간 최적화 및 순회 경로 엔진

> **가출·위기 청소년 복지 사각지대 해소를 위한 복합취약지수(CVI) 매핑 및 이동형 쉼터 최적 경로 선정 플랫폼**
>
> [![Live Demo](https://img.shields.io/badge/demo-online-brightgreen.svg)](https://dohye0508.github.io/focus-hub-voronoi/)
> [![Tech Stack](https://img.shields.io/badge/stack-JS%20%7C%20Leaflet%20%7C%20Python-blue.svg)](#)
> [![License](https://img.shields.io/badge/license-MIT-green.svg)](#)

---

## 🚀 실시간 데모 및 웹 서비스 링크
브라우저에서 실시간 공간 최적화 연산을 직접 실행해 볼 수 있습니다:
👉 **[https://dohye0508.github.io/focus-hub-voronoi/](https://dohye0508.github.io/focus-hub-voronoi/)**

---

## 💡 핵심 개요

**Focus-Hub Voronoi**는 공공데이터를 기반으로 청소년 밀집 및 위기 지역의 사각지대를 도출하고, 브라우저 단에서 실시간 공간 최적화 알고리즘을 수행하여 **이동형 쉼터 차량(버스)의 최적 정차 거점과 순회 경로를 제안**하는 경량화 서버리스(Serverless) 공간 분석 플랫폼입니다.

---

## ⚡ 주요 공간 알고리즘 파이프라인

본 플랫폼은 한정된 복지 자원을 가장 과학적이고 효율적으로 배분하기 위해 수학적으로 엄격하게 설계된 4단계 최적화 엔진을 가동합니다.

```
[공간 데이터 집계] ──> [로지스틱 회귀 CVI 산출] ──> [MAUP 방지형 KDE 밀도 분석]
                                                                    │
[사용자 브라우저 렌더링] <── [Metric TSP 순회 경로 최적화] <── [p-Median 입지 선정]
```

### 1. 로지스틱 회귀분석(Logistic Regression) 기반 복합취약지수 (CVI)
CVI의 정확한 분석을 위해 연구자의 주관적인 임의 가중치를 배제하고, 위기 청소년 밀집 여부(종속변수 $Y$)를 모델링하는 **로지스틱 회귀분석**을 수행하여 데이터 기반의 가중치를 정밀 산출했습니다.

$$\log\left(\frac{P(Y=1)}{1-P(Y=1)}\right) = \beta_0 + \beta_1 A + \beta_2 S + \beta_3 P$$

회귀분석 결과 도출된 Odds Ratio 비중에 따라 최종 변수별 가중치를 다음과 같이 정규화하여 반영했습니다.
- **$w_A$ (0.53)**: 학원 밀집도 (유동 인구 및 심야 시간 체류 밀도를 반영하는 대리 지표)
- **$w_S$ (0.30)**: 지역별 스트레스 인지율 (가출 및 위기 발생 잠재 위험도)
- **$w_P$ (0.17)**: 청소년 주민등록 인구 (해당 권역의 배후 수요 규모)

$$\text{CVI}(i) = 0.53 \cdot \tilde{A}(i) + 0.30 \cdot \tilde{S}(i) + 0.17 \cdot \tilde{P}(i)$$
(단, $\tilde{X}$는 Min-Max 정규화된 공간 데이터 변수)

### 2. MAUP 공간 오류 방지형 커널 밀도 추정 (KDE)
고정된 행정구역(동/구) 경계선을 기준으로 데이터를 단순 합산하면 경계 인접 부근의 밀집 데이터가 분산되거나 왜곡되는 **MAUP(공간단위 수정의 문제)**에 빠지게 됩니다. 

본 프로젝트는 이 한계를 극복하기 위해 모든 점(Point) 데이터에 **가우시안 커널(Gaussian Kernel)**을 적용하여 연속적인 공간 확률 밀도 지도를 생성합니다.
$$\hat{f}(x) = \frac{1}{nh} \sum_{i=1}^{n} K\!\left(\frac{x - x_i}{h}\right)$$
이를 통해 경계선 오류 없이 **"청소년 밀집도는 폭발적이지만 복지 인프라 혜택이 미치지 못하는 실질적인 사각지대(Red Zone)"**를 정밀 타겟팅합니다.

### 3. p-Median 모델을 통한 정차 거점 선정 (Location-Allocation)
가용 가능한 $p$개의 이동형 쉼터 버스를 배치하여 핫스팟 대상 청소년들의 물리적 총 이동 거리를 최소화하는 입지를 선택합니다.
$$\min_{F \subseteq X,\, |F|=p} \sum_{i \in D} w_i \cdot \min_{j \in F} d(i, j)$$
이 입지-할당(Location-Allocation) NP-hard 문제를 브라우저 런타임에서 신속하게 해결하기 위해 CVI 가중치를 적용한 **k-Means 클러스터링 알고리즘**을 활용합니다.
- **형평성 파라미터 ($\lambda$) 탑재**: 정책 입안자가 슬라이더를 통해 **효율성($\lambda = 0$, 밀집 지역 위주)**과 **형평성($\lambda = 1$, 외곽 소외 지역 포용)**의 가중치를 인공지능에 직접 반영할 수 있도록 설계하여 설명 가능한 AI(Explainable AI)를 구현했습니다.

### 4. 이동형 쉼터 순회 경로 최적화 (Metric TSP - Christofides)
p-Median으로 도출된 최종 핫스팟들을 이동형 쉼터 차량이 순차적으로 방문할 수 있도록 **외판원 문제(Traveling Salesperson Problem)**로 모델링합니다. 
차량이 운행하는 2차원 Euclidean 평면은 **삼각 부등식(Triangle Inequality)**($d(x,y) \le d(x,z) + d(z,y)$)을 만족하므로, 다항 시간 내에 전역 최적 정답의 **1.5배 이내의 최단 거리를 무조건 보장하는 크리스토피데스 알고리즘(Christofides Algorithm)**을 적용하여 효율적인 순회 노선(Patrol Route)을 제시합니다.

---

## 🛠 아키텍처 및 기술 스택

- **클라이언트 런타임**: Pure HTML5/CSS3 (Glassmorphism), Vanilla JavaScript (ES6+), Leaflet.js (공간 맵 렌더링), Turf.js (클라이언트 내 공간 연산).
- **데이터 파이프라인**: Python 3.12 (GeoPandas, SciPy, NumPy, Shapely) 기반 분석 파이프라인을 구축하여 무거운 GIS 공간 연산 및 회귀분석 처리를 선행하고, 이를 브라우저 친화적인 JSON 포맷(`cells.json`, `shelters.json`)으로 정적 캐싱.
- **호스팅 & 배포**: GitHub Pages를 통한 서버리스(Serverless) 단일 페이지 애플리케이션(SPA) 호스팅 및 Progressive Web App (PWA) 적용으로 오프라인 및 모바일 환경 최적화.

---

## 💻 로컬 빌드 및 시작 가이드

### 필수 요구사항
- Python 3.10+ (데이터셋 전처리 및 재생성 시에만 필요)
- 최신 웹 브라우저

### 로컬에서 앱 구동하기
서버리스 정적 웹앱 구조이므로, 별도의 복잡한 백엔드 설치 없이 로컬 웹 서버 구동 명령만으로 즉시 구동 가능합니다.
```bash
# 저장소 복제
git clone https://github.com/dohye0508/focus-hub-voronoi.git
cd focus-hub-voronoi

# 내장 파이썬 웹 서버 실행
python -m http.server 8000
```
브라우저 주소창에 **`http://localhost:8000`**을 입력하여 접속합니다.

### 공간 데이터 컴파일 (선택 사항)
`data/raw/` 내의 공공데이터 원본 CSV 파일을 변경한 뒤, 압축 캐시 파일(`cells.json`, `shelters.json`)을 빌드하려는 경우:
```bash
# 종속 라이브러리 설치
pip install -r requirements.txt

# 전처리 및 전처리 결과 캐싱 스크립트 실행
python scripts/export_data.py
```

---

## 🎨 주요 시각화 기능
- **거미줄 할당 시각화 (Spider Web)**: 각 청소년 생활권(Cell)이 어떤 쉼터 거점의 커버리지를 받고 있는지 실시간 거미줄 점선망으로 표현.
- **도보 커버리지 반경 표시**: 쉼터 거점 주변 2km 반경(도보 30분 거리)의 원형 범위를 시각화하여 사각지대 지수를 정량화.
- **내 위치 기반(GPS) 응급 조회**: 모바일 기기의 실시간 GPS를 수신하여 현재 접속 위치 주변 10km 이내의 쉼터 차량 정보와 소속 구역의 취약 지수를 안내하는 모달 창 구현.

---

## 📄 라이선스
본 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하십시오.
