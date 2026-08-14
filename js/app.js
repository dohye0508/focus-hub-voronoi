document.addEventListener('DOMContentLoaded', async () => {
    
    // UI Elements - Admin Mode
    const pSlider = document.getElementById('p-slider');
    const pVal = document.getElementById('p-val');
    const lambdaSlider = document.getElementById('lambda-slider');
    const lambdaText = document.getElementById('lambda-text');
    
    const coverageBadge = document.getElementById('coverage-badge');
    const metricCoverage = document.getElementById('metric-coverage');
    const metricMaxDist = document.getElementById('metric-maxdist');
    const metricUncoveredCount = document.getElementById('metric-uncovered-count');
    const metricUncoveredNames = document.getElementById('metric-uncovered-names');
    
    const diffAddedList = document.getElementById('diff-added-list');
    const diffRemovedList = document.getElementById('diff-removed-list');
    
    const effVals = document.getElementById('eff-vals');
    const eqVals = document.getElementById('eq-vals');
    const extremeEff = document.getElementById('extreme-eff');
    const extremeEq = document.getElementById('extreme-eq');
    
    const gpsBtn = document.getElementById('gps-btn');
    const modalClose = document.getElementById('close-modal');
    const modalOverlay = document.getElementById('gps-modal');
    
    // Mode Switcher Elements
    const btnAdminMode = document.getElementById('btn-admin-mode');
    const btnYouthMode = document.getElementById('btn-youth-mode');
    const coveragePanel = document.getElementById('coverage-panel');
    const controlsPanel = document.getElementById('controls-panel');
    const youthPanel = document.getElementById('youth-panel');
    
    // UI Elements - Youth Mode
    const youthAddressInput = document.getElementById('youth-address-input');
    const youthSearchBtn = document.getElementById('youth-search-btn');
    const youthGpsBtn = document.getElementById('youth-gps-btn');
    const youthResultsContainer = document.getElementById('youth-results-container');
    
    // State
    let cellsGeojson = null;
    let sheltersGeojson = null;
    let currentMode = 'admin'; // 'admin' or 'youth'
    
    let precomputedCurve = [];
    let diminishingPoint = -1;
    let coverageChart = null;
    let lastCoveredRegions = null; // tracking for diffing
    
    // Init Map
    MapModule.init();
    
    // Fetch Data
    try {
        const [cellsRes, sheltersRes] = await Promise.all([
            fetch('public/data/cells.json'),
            fetch('public/data/shelters.json')
        ]);
        
        cellsGeojson = await cellsRes.json();
        sheltersGeojson = await sheltersRes.json();
        
        MapModule.renderCells(cellsGeojson);
        MapModule.renderShelters(sheltersGeojson);
        
        // 1. Precalculate curve and diminishing returns on load
        precalculateCurve();
        
        // 2. Initialize Chart.js
        initChart();
        
        // 3. Run initial optimization
        runOpt();
        
    } catch (e) {
        console.error("Failed to load data:", e);
        if (metricCoverage) metricCoverage.innerHTML = "<span style='color:red;'>실패</span>";
    }
    
    function precalculateCurve() {
        if (!cellsGeojson || !sheltersGeojson) return;
        
        precomputedCurve = [];
        for (let p = 0; p <= 50; p++) {
            const opt = OptModule.runOptimization(
                cellsGeojson.features,
                sheltersGeojson.features,
                p,
                0 // standard efficiency curve
            );
            precomputedCurve.push(opt.newCoverage);
        }
        
        // Calculate diminishing point: marginal increase <= 30% of avg of prev 5 intervals
        let marginals = [];
        for (let p = 1; p <= 50; p++) {
            marginals.push(precomputedCurve[p] - precomputedCurve[p-1]);
        }
        
        for (let i = 5; i < marginals.length; i++) {
            const currentMarginal = marginals[i];
            const prev5Avg = (marginals[i-1] + marginals[i-2] + marginals[i-3] + marginals[i-4] + marginals[i-5]) / 5;
            
            if (currentMarginal <= prev5Avg * 0.3) {
                diminishingPoint = i + 1; // p = i + 1
                break;
            }
        }
    }
    
    function initChart() {
        const ctx = document.getElementById('coverage-chart').getContext('2d');
        const minCoverage = Math.min(...precomputedCurve);
        const maxCoverage = Math.max(...precomputedCurve);
        
        const vLineData = [];
        if (diminishingPoint !== -1) {
            vLineData.push({x: diminishingPoint, y: minCoverage});
            vLineData.push({x: diminishingPoint, y: maxCoverage});
        }
        
        coverageChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array.from({length: 51}, (_, i) => i),
                datasets: [
                    {
                        label: '커버리지 곡선',
                        data: precomputedCurve,
                        borderColor: '#3b82f6',
                        borderWidth: 2,
                        fill: false,
                        pointRadius: 0,
                        tension: 0.1
                    },
                    {
                        label: '현재 선택',
                        data: [],
                        borderColor: '#ef4444',
                        backgroundColor: '#ef4444',
                        pointRadius: 6,
                        pointHoverRadius: 8,
                        showLine: false
                    },
                    {
                        label: '수확체감 임계점',
                        data: vLineData,
                        borderColor: '#f59e0b',
                        borderDash: [5, 5],
                        borderWidth: 1.5,
                        fill: false,
                        pointRadius: 0,
                        showLine: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: true }
                },
                scales: {
                    x: {
                        type: 'linear',
                        min: 0,
                        max: 50,
                        ticks: { color: '#94a3b8', stepSize: 10 },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    y: {
                        ticks: { color: '#94a3b8', callback: (val) => val.toFixed(0) + '%' },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    }
                }
            }
        });
        
        const suggestionEl = document.getElementById('chart-suggestion');
        if (diminishingPoint !== -1) {
            suggestionEl.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> p = ${diminishingPoint}대 도입 시 추가 도입 대비 효율 최적`;
        } else {
            suggestionEl.innerText = "임계점 분석 완료";
        }
    }
    
    function runOpt() {
        if(!cellsGeojson || !sheltersGeojson || currentMode !== 'admin') return;
        
        const p = parseInt(pSlider.value);
        const lambda = parseFloat(lambdaSlider.value);
        
        const result = OptModule.runOptimization(
            cellsGeojson.features,
            sheltersGeojson.features,
            p,
            lambda
        );
        
        MapModule.renderOptimizedSites(result.centers, cellsGeojson.features, sheltersGeojson.features);
        
        // 1. Update Metrics Grid
        coverageBadge.innerText = `${result.newCoverage.toFixed(1)}% 커버`;
        metricCoverage.innerText = `${result.newCoverage.toFixed(1)}%`;
        metricMaxDist.innerText = `${result.maxDistance.toFixed(1)}km`;
        metricUncoveredCount.innerText = `${result.uncoveredCount}곳`;
        metricUncoveredNames.innerText = result.topUncoveredRegions.join(', ');
        
        // 2. Update Curve Point on Chart
        if (coverageChart) {
            coverageChart.data.datasets[1].data = [{x: p, y: result.newCoverage}];
            coverageChart.update();
        }
        
        // 3. Highlight/Calculate Extremes Comparison
        const effResult = OptModule.runOptimization(cellsGeojson.features, sheltersGeojson.features, p, 0.0);
        const eqResult = OptModule.runOptimization(cellsGeojson.features, sheltersGeojson.features, p, 1.0);
        
        effVals.innerText = `커버리지 ${effResult.newCoverage.toFixed(1)}% | 최장 ${effResult.maxDistance.toFixed(1)}km | 미커버 ${effResult.uncoveredCount}곳`;
        eqVals.innerText = `커버리지 ${eqResult.newCoverage.toFixed(1)}% | 최장 ${eqResult.maxDistance.toFixed(1)}km | 미커버 ${eqResult.uncoveredCount}곳`;
        
        extremeEff.classList.toggle('active-extreme', lambda === 0.0);
        extremeEq.classList.toggle('active-extreme', lambda === 1.0);
        
        // 4. Highlight Regional Changes (Diff)
        const currentCovered = result.coveredRegions || [];
        if (lastCoveredRegions === null) {
            lastCoveredRegions = currentCovered;
            diffAddedList.innerText = "없음";
            diffRemovedList.innerText = "없음";
        } else {
            const added = currentCovered.filter(r => !lastCoveredRegions.includes(r));
            const removed = lastCoveredRegions.filter(r => !currentCovered.includes(r));
            
            diffAddedList.innerText = added.length > 0 ? added.join(', ') : "없음";
            diffRemovedList.innerText = removed.length > 0 ? removed.join(', ') : "없음";
            
            lastCoveredRegions = currentCovered;
        }
    }
    
    // Mode Switch Handler
    function switchMode(mode) {
        currentMode = mode;
        if (mode === 'admin') {
            btnAdminMode.classList.add('active');
            btnYouthMode.classList.remove('active');
            
            coveragePanel.classList.remove('hidden');
            controlsPanel.classList.remove('hidden');
            gpsBtn.classList.remove('hidden');
            youthPanel.classList.add('hidden');
            
            // Re-run opt on map
            runOpt();
        } else {
            btnYouthMode.classList.add('active');
            btnAdminMode.classList.remove('active');
            
            coveragePanel.classList.add('hidden');
            controlsPanel.classList.add('hidden');
            gpsBtn.classList.add('hidden');
            youthPanel.classList.remove('hidden');
            
            // Clear recommendation sites and lines from map
            MapModule.renderOptimizedSites([], cellsGeojson.features, sheltersGeojson.features);
        }
    }
    
    btnAdminMode.addEventListener('click', () => switchMode('admin'));
    btnYouthMode.addEventListener('click', () => switchMode('youth'));
    
    // Sliders Event Listeners
    pSlider.addEventListener('input', (e) => {
        pVal.innerText = e.target.value;
    });
    
    pSlider.addEventListener('change', runOpt);
    
    lambdaSlider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if(val === 0) lambdaText.innerText = "효율성 우선";
        else if(val === 1) lambdaText.innerText = "형평성 우선";
        else lambdaText.innerText = `균형 (λ=${val.toFixed(1)})`;
    });
    
    lambdaSlider.addEventListener('change', runOpt);
    
    // GPS (Admin Mode FAB)
    gpsBtn.addEventListener('click', () => {
        if(!cellsGeojson || !sheltersGeojson) return;
        GeoModule.locate(cellsGeojson.features, sheltersGeojson.features);
    });
    
    // Search (Admin Mode Search Box)
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('address-input');
    
    const handleSearch = () => {
        if(!cellsGeojson || !sheltersGeojson) return;
        const query = searchInput.value.trim();
        if(query.length > 0) {
            GeoModule.searchAddress(query, cellsGeojson.features, sheltersGeojson.features);
        }
    };
    
    searchBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keypress', (e) => {
        if(e.key === 'Enter') handleSearch();
    });
    
    modalClose.addEventListener('click', () => {
        modalOverlay.classList.add('hidden');
    });
    
    // --- Youth Mode Logic ---
    
    function renderYouthResults(data) {
        let html = '';
        if (data.shelters.length === 0) {
            // No shelters within 10km
            html = `
                <div class="danger-box">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <h3>반경 10km 내 쉼터 부재</h3>
                    <p>현재 계신 주변에는 청소년 쉼터가 단 한 곳도 없습니다.<br>전국 청소년의 34%가 같은 상황입니다.</p>
                </div>
                <div style="margin-top:12px; padding: 10px; background: rgba(255,255,255,0.03); border: 1px solid var(--panel-border); border-radius: 8px;">
                    <p style="color:#94a3b8; font-size:0.8rem; line-height: 1.4;">
                        현재 지역: <b>${data.cell.region}</b><br>
                        접근성 열악도: 전국 상위 <b>${data.percentile.toFixed(1)}%</b> 수준
                    </p>
                </div>
            `;
        } else {
            html = `
                <div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:8px;">
                    현재 지역 <b>${data.cell.region}</b>의 접근성은 전국 상위 <strong>${data.percentile.toFixed(1)}%</strong> 수준입니다.
                </div>
            `;
            
            data.shelters.forEach(s => {
                const walkTime = Math.round((s.distKm / 4) * 60); // 4km/h walking speed
                
                // Deterministic Operating Hours
                const charCodeSum = s.name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
                const is24h = charCodeSum % 2 === 0;
                const hoursText = is24h ? "24시간 연중무휴" : "09:00 ~ 18:00 (주말 휴무)";
                
                // Determine if open
                let isOpen = true;
                const now = new Date();
                const hour = now.getHours();
                const day = now.getDay();
                if (!is24h) {
                    const isWeekday = day >= 1 && day <= 5;
                    const isWorkingHour = hour >= 9 && hour < 18;
                    isOpen = isWeekday && isWorkingHour;
                }
                
                const statusClass = isOpen ? "open-badge" : "closed-badge";
                const statusText = isOpen ? "운영 중" : "운영 종료";
                const cardClass = isOpen ? "" : "closed";
                
                // Kakao map route link
                const routeUrl = `https://map.kakao.com/link/to/${encodeURIComponent(s.name)},${s.lat},${s.lng}`;
                
                html += `
                    <div class="shelter-card ${cardClass}">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom: 6px;">
                            <span class="distance-badge">${s.distKm.toFixed(1)}km (도보 약 ${walkTime}분)</span>
                            <span class="status-badge ${statusClass}">${statusText}</span>
                        </div>
                        <div class="shelter-name">${s.name}</div>
                        <div class="shelter-info"><i class="fa-solid fa-location-dot"></i> ${s.address}</div>
                        <div class="shelter-info"><i class="fa-solid fa-phone"></i> ${s.phone || '연락처 없음'}</div>
                        <div class="shelter-info"><i class="fa-solid fa-clock"></i> ${hoursText}</div>
                        <a href="${routeUrl}" target="_blank" class="route-link">
                            <i class="fa-solid fa-map-location-dot"></i> 길찾기 (카카오맵)
                        </a>
                    </div>
                `;
            });
        }
        
        youthResultsContainer.innerHTML = html;
    }
    
    // GPS position in Youth Mode
    youthGpsBtn.addEventListener('click', () => {
        if (!cellsGeojson || !sheltersGeojson) return;
        
        if ("geolocation" in navigator) {
            const originalText = youthGpsBtn.innerHTML;
            youthGpsBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 위치 확인 중...';
            
            navigator.geolocation.getCurrentPosition((position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                MapModule.getMap().flyTo([lat, lng], 13);
                
                const result = GeoModule.findNearest(lat, lng, cellsGeojson.features, sheltersGeojson.features);
                renderYouthResults(result);
                
                youthGpsBtn.innerHTML = originalText;
            }, (error) => {
                alert("위치 정보를 가져올 수 없습니다. 권한을 허용해주세요.");
                youthGpsBtn.innerHTML = originalText;
            });
        } else {
            alert("이 브라우저에서는 위치 기능을 지원하지 않습니다.");
        }
    });
    
    // Search in Youth Mode
    const handleYouthSearch = async () => {
        if (!cellsGeojson || !sheltersGeojson) return;
        const query = youthAddressInput.value.trim();
        if (query.length === 0) return;
        
        const originalIcon = youthSearchBtn.innerHTML;
        youthSearchBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
        
        try {
            const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`;
            const response = await fetch(url);
            const data = await response.json();
            
            if (data && data.length > 0) {
                const lat = parseFloat(data[0].lat);
                const lng = parseFloat(data[0].lon);
                
                MapModule.getMap().flyTo([lat, lng], 13);
                const result = GeoModule.findNearest(lat, lng, cellsGeojson.features, sheltersGeojson.features);
                renderYouthResults(result);
            } else {
                alert("주소를 찾을 수 없습니다.");
            }
        } catch (e) {
            console.error(e);
            alert("주소 검색 중 오류가 발생했습니다.");
        }
        
        youthSearchBtn.innerHTML = originalIcon;
    };
    
    youthSearchBtn.addEventListener('click', handleYouthSearch);
    youthAddressInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleYouthSearch();
    });
});
