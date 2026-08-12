# Focus-Hub Voronoi: Real-Time Spatial Optimization Engine for Mobile Youth Shelters

> **A Serverless, High-Tech Decision Support Platform for Vulnerability Indexing and Patrol Route Optimization**
>
> [![Live Demo](https://img.shields.io/badge/demo-online-brightgreen.svg)](https://dohye0508.github.io/focus-hub-voronoi/)
> [![Tech Stack](https://img.shields.io/badge/stack-JS%20%7C%20Leaflet%20%7C%20Python-blue.svg)](#)
> [![License](https://img.shields.io/badge/license-MIT-green.svg)](#)

---

## 🚀 Live Demo & Interactive Interface
Explore the live optimization engine directly from your browser:
👉 **[https://dohye0508.github.io/focus-hub-voronoi/](https://dohye0508.github.io/focus-hub-voronoi/)**

---

## 💡 Overview

**Focus-Hub Voronoi** is an open-source, serverless spatial analysis engine designed to optimize the stationary deployment points (hubs) and patrol routing of mobile youth shelters. By leveraging public datasets and client-side high-performance spatial computing, the platform bridges the gap between static social services and dynamic, high-density youth populations.

---

## ⚡ Core Computational Pipeline

The platform utilizes a multi-stage optimization pipeline to ensure mathematically rigorous and computationally efficient allocation of mobile resources:

```
[Spatial Data Aggregation] ──> [Logistic Regression CVI] ──> [MAUP-Aware KDE]
                                                                    │
[Client-Side Leaflet & PWA] <── [Metric TSP Routing] <── [p-Median Optimization]
```

### 1. Logistic Regression-Weighted CVI (Composite Vulnerability Index)
Rather than using arbitrary subjective weights, the platform calculates CVI using weights objectively derived from multivariate **Logistic Regression** modeling:
$$\log\left(\frac{P(Y=1)}{1-P(Y=1)}\right) = \beta_0 + \beta_1 A + \beta_2 S + \beta_3 P$$
Using odds ratios calculated from regional crisis indicators, the normalized weights are configured as:
- **$w_A$ (0.53)**: Academy Density (Proxy for youth concentration and study patterns)
- **$w_S$ (0.30)**: Regional Stress Index (Trigger potential for runaway behavior)
- **$w_P$ (0.17)**: Youth Demographic Scale (Resident population benchmark)

$$\text{CVI}(i) = 0.53 \cdot \tilde{A}(i) + 0.30 \cdot \tilde{S}(i) + 0.17 \cdot \tilde{P}(i)$$

### 2. MAUP-Aware Kernel Density Estimation (KDE)
Aggregating discrete point data into administrative boundaries leads to the **Modifiable Areal Unit Problem (MAUP)**. We solve this by implementing a **Gaussian KDE** smoothing model, converting point data into a continuous probability density surface:
$$\hat{f}(x) = \frac{1}{nh} \sum_{i=1}^{n} K\!\left(\frac{x - x_i}{h}\right)$$
This enables exact, borderless identification of "welfare inversion hotspots"—areas with critical youth densities but zero existing shelter infrastructure.

### 3. Location-Allocation via p-Median Optimization
To select $p$ stationary hubs for mobile shelters that minimize the total travel distance of the target population:
$$\min_{F \subseteq X,\, |F|=p} \sum_{i \in D} w_i \cdot \min_{j \in F} d(i, j)$$
This NP-hard problem is solved in real-time in the browser using a CVI-weighted **K-Means Clustering Centroid** approximation. 
- **Adaptive Policy Parameter ($\lambda$)**: Allows policymakers to balance **Efficiency ($\lambda = 0$, dense center focus)** vs. **Equity ($\lambda = 1$, remote boundary coverage)** in real-time.

### 4. Vehicle Patrol Routing (Metric TSP & Christofides 1.5-Approximation)
Once the optimal hubs are established, the path of the patrol vehicle is modeled as a **Metric Traveling Salesperson Problem (Metric TSP)**. Because the vehicle operates in a 2D Euclidean space, the **Triangle Inequality** ($d(x,y) \le d(x,z) + d(z,y)$) holds.
We apply the **Christofides Algorithm**, guaranteeing a polynomial-time patrol route that is mathematically bounded to **at most 1.5 times the optimal minimum distance**.

---

## 🛠 Tech Stack & Architecture

- **Frontend Interface**: Pure JavaScript (ES6+), Leaflet.js (Interactive Mapping), Turf.js (Spatial Calculations), CSS3 Glassmorphic UI/UX.
- **Backend/Data Engine**: Pre-baked spatial pipelines written in Python 3.12 (GeoPandas, SciPy, NumPy, Shapely) compiling raw datasets into optimized static payloads (`cells.json`, `shelters.json`).
- **Deployment**: Serverless SPA hosted via GitHub Pages, with native progressive web application (PWA) manifest support for offline responsiveness.

---

## 💻 Local Development & Setup

### Prerequisites
- Python 3.10+ (Only required for regenerating datasets)
- Modern web browser

### Running the App Locally
Since the V2 architecture is entirely serverless, you can run the app without any heavyweight web servers:
```bash
# Clone the repository
git clone https://github.com/dohye0508/focus-hub-voronoi.git
cd focus-hub-voronoi

# Run a simple local HTTP server
python -m http.server 8000
```
Open **`http://localhost:8000`** in your browser.

### Data Compilation (Optional)
If you modify raw public CSV files in `data/raw/` and wish to rebuild the cached JSON files:
```bash
# Install dependencies
pip install -r requirements.txt

# Run preprocessing and caching script
python scripts/export_data.py
```

---

## 🚀 Key User Interface Features

- **Dynamic Visual Analytics**: Displays spider-web allocation lines (connecting hotspots to their respective optimal hubs) and 2km walkability radiuses dynamically on the map.
- **Explainable Policy Control Panels**: Left-aligned transparent panels featuring real-time sliders for parameter adjustments ($p$ and $\lambda$) with immediate visual feedback.
- **GPS-enabled Emergency Services FAB**: A high-impact floating action button utilizing browser Geolocation APIs to calculate distances and walking times to the nearest mobile shelter from the user's real-time position.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
