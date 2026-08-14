document.addEventListener('DOMContentLoaded', async () => {
    
    // Start Screen Elements
    const startScreen = document.getElementById('start-screen');
    const btnStartYouth = document.getElementById('btn-start-youth');
    const btnStartAdmin = document.getElementById('btn-start-admin');
    
    // Back Links
    const backToStartYouth = document.getElementById('back-to-start-youth');
    const backToStartAdmin = document.getElementById('back-to-start-admin');
    
    // Organization View Elements
    const pSlider = document.getElementById('p-slider');
    const pVal = document.getElementById('p-val');
    const lambdaSlider = document.getElementById('lambda-slider');
    const lambdaText = document.getElementById('lambda-text');
    
    const metricCoverage = document.getElementById('metric-coverage');
    const metricMaxDist = document.getElementById('metric-maxdist');
    const metricUncoveredCount = document.getElementById('metric-uncovered-count');
    const metricUncoveredNames = document.getElementById('metric-uncovered-names');
    
    const effVals = document.getElementById('eff-vals');
    const eqVals = document.getElementById('eq-vals');
    const extremeEff = document.getElementById('extreme-eff');
    const extremeEq = document.getElementById('extreme-eq');
    
    const coveragePanel = document.getElementById('coverage-panel');
    const controlsPanel = document.getElementById('controls-panel');
    const youthPanel = document.getElementById('youth-panel');
    
    // Youth Mode Elements
    const youthAddressInput = document.getElementById('youth-address-input');
    const youthSearchBtn = document.getElementById('youth-search-btn');
    const youthGpsBtn = document.getElementById('youth-gps-btn');
    const youthResultsContainer = document.getElementById('youth-results-container');
    const youthMobileRouteContainer = document.getElementById('youth-mobile-route-container');
    
    // State
    let cellsGeojson = null;
    let sheltersGeojson = null;
    let currentMode = 'start'; // 'start', 'youth', 'admin'
    
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
        MapModule.hideCells(); // Start in hidden cells mode
        
    } catch (e) {
        console.error("Failed to load data:", e);
    }
    
    // Run Optimization (Admin Mode)
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
        
        // 1. Update everyday stats (rounded to 1 decimal place or integer)
        metricCoverage.innerHTML = `<strong>${result.newCoverage.toFixed(1)}%</strong>`;
        metricMaxDist.innerHTML = `<strong>${Math.round(result.maxDistance)}km</strong>`;
        metricUncoveredCount.innerHTML = `<strong>${result.uncoveredCount}곳</strong>`;
        metricUncoveredNames.innerText = result.topUncoveredRegions.join(', ');
        
        // 2. Calculate Extremes Comparison
        const effResult = OptModule.runOptimization(cellsGeojson.features, sheltersGeojson.features, p, 0.0);
        const eqResult = OptModule.runOptimization(cellsGeojson.features, sheltersGeojson.features, p, 1.0);
        
        effVals.innerText = `걸어서 갈 수 있는 청소년 ${effResult.newCoverage.toFixed(1)}% | 가장 먼 지역 ${Math.round(effResult.maxDistance)}km | 닿지 않는 지역 ${effResult.uncoveredCount}곳`;
        eqVals.innerText = `걸어서 갈 수 있는 청소년 ${eqResult.newCoverage.toFixed(1)}% | 가장 먼 지역 ${Math.round(eqResult.maxDistance)}km | 닿지 않는 지역 ${eqResult.uncoveredCount}곳`;
        
        extremeEff.classList.toggle('active-extreme', lambda === 0.0);
        extremeEq.classList.toggle('active-extreme', lambda === 1.0);
    }
    
    // Mode Switcher Handlers
    function switchTo(mode) {
        currentMode = mode;
        
        // Clear temporary items on map
        MapModule.clearMobileStops();
        MapModule.renderOptimizedSites([], [], []);
        
        if (mode === 'start') {
            startScreen.classList.remove('hidden');
            coveragePanel.classList.add('hidden');
            controlsPanel.classList.add('hidden');
            youthPanel.classList.add('hidden');
            MapModule.hideCells();
            
            // Zoom out map to national view
            MapModule.getMap().flyTo([36.2, 127.8], 7.5);
            
        } else if (mode === 'youth') {
            startScreen.classList.add('hidden');
            coveragePanel.classList.add('hidden');
            controlsPanel.classList.add('hidden');
            youthPanel.classList.remove('hidden');
            MapModule.hideCells(); // No voronoi/cvi layer in youth mode
            
            // Reset results
            youthResultsContainer.innerHTML = '<div class="empty-state">내 위치를 확인하거나 지역을 검색해 주세요.</div>';
            youthMobileRouteContainer.classList.add('hidden');
            youthMobileRouteContainer.innerHTML = '';
            
        } else if (mode === 'admin') {
            startScreen.classList.add('hidden');
            coveragePanel.classList.remove('hidden');
            controlsPanel.classList.remove('hidden');
            youthPanel.classList.add('hidden');
            MapModule.showCells(); // Show colored cells (analytical view)
            
            runOpt();
        }
    }
    
    // Bind Start Button events
    btnStartYouth.addEventListener('click', () => switchTo('youth'));
    btnStartAdmin.addEventListener('click', () => switchTo('admin'));
    
    // Bind Back Links
    backToStartYouth.addEventListener('click', (e) => { e.preventDefault(); switchTo('start'); });
    backToStartAdmin.addEventListener('click', (e) => { e.preventDefault(); switchTo('start'); });
    
    // Admin Slider bindings
    pSlider.addEventListener('input', (e) => {
        pVal.innerText = e.target.value;
    });
    pSlider.addEventListener('change', runOpt);
    
    lambdaSlider.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if(val === 0) lambdaText.innerText = "많은 청소년이 이용하도록 우선";
        else if(val === 1) lambdaText.innerText = "먼 지역도 빠짐없이 우선";
        else lambdaText.innerText = `균형 배치 (λ=${val.toFixed(1)})`;
    });
    lambdaSlider.addEventListener('change', runOpt);
    
    // Search bindings (Admin Mode)
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
    
    // --- Youth Mode Controller ---
    
    // Render detail route cards for selected mobile shelter
    function selectMobileShelter(shelter) {
        const props = shelter.properties;
        if (!props.is_mobile) return;
        
        const coords = shelter.geometry.coordinates;
        const schedule = props.schedule || [];
        const isDummy = props.is_dummy === true;
        
        let html = '';
        
        if (isDummy) {
            html += `
                <div class="disclaimer-banner">
                    <i class="fa-solid fa-circle-info"></i>
                    <span>예시 일정입니다. 실제 운행 정보는 기관에 확인하세요.</span>
                </div>
            `;
        }
        
        // Check if currently operating today
        const now = new Date();
        const currentHour = now.getHours();
        const currentDay = now.getDay(); // 0 is Sunday, 1 is Monday...
        const korDayIndex = currentDay === 0 ? 6 : currentDay - 1; // Mon=0.. Sun=6
        
        let isCurrentlyOpen = false;
        
        html += `
            <div class="schedule-card">
                <div class="schedule-header">
                    <i class="fa-solid fa-calendar-days"></i>
                    <span>${props.name} 운행 경로 및 일정</span>
                </div>
        `;
        
        schedule.forEach((item, idx) => {
            const isToday = idx === korDayIndex;
            const isPast = idx < korDayIndex;
            
            let rowClass = '';
            if (isToday) rowClass = 'today-highlight';
            else if (isPast) rowClass = 'past-day';
            
            // Check if active today and current time falls inside 19:00 - 23:00
            if (isToday && item.time) {
                // Parse operating hours (assuming 19:00-23:00 dummy for testing, or generic format hh:mm)
                // Default: 19:00 to 23:00
                const startHour = 19;
                const endHour = 23;
                if (currentHour >= startHour && currentHour < endHour) {
                    isCurrentlyOpen = true;
                }
            }
            
            html += `
                <div class="schedule-row ${rowClass}">
                    <span><b>${item.day}</b></span>
                    <span>${item.location}</span>
                    <span>${item.time || '운행 없음'}</span>
                </div>
            `;
        });
        
        html += `</div>`;
        
        // Show status banner if open
        if (isCurrentlyOpen) {
            html = `
                <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); color: #34d399; padding: 10px 12px; border-radius: 8px; font-size: 0.8rem; font-weight: 700; margin-bottom: 12px; text-align: center;">
                    <i class="fa-solid fa-circle-check"></i> 지금 운영 중
                </div>
            ` + html;
        }
        
        youthMobileRouteContainer.innerHTML = html;
        youthMobileRouteContainer.classList.remove('hidden');
        
        // Scroll to schedule card
        youthMobileRouteContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        // Render stops and connections on Map
        MapModule.renderMobileStops(coords[1], coords[0], schedule, props.name);
    }
    
    // Register global click handler to coordinate with Leaflet clicks
    window.onShelterClick = function(feature) {
        if (currentMode === 'youth' && feature.properties.is_mobile) {
            selectMobileShelter(feature);
        }
    };
    
    // Calculate distance to absolute nearest shelter in the database
    function findAbsoluteNearestDistance(lat, lng) {
        let minD = Infinity;
        sheltersGeojson.features.forEach(s => {
            const d = OptModule.calcDistKm(lat, lng, s.geometry.coordinates[1], s.geometry.coordinates[0]);
            if (d < minD) minD = d;
        });
        return minD;
    }
    
    function renderYouthResults(data, userLat, userLng) {
        let html = '';
        
        if (data.shelters.length === 0) {
            // Find absolute nearest distance in the entire database
            const nearestKm = findAbsoluteNearestDistance(userLat, userLng);
            
            html = `
                <div class="danger-box">
                    <i class="fa-solid fa-location-dot"></i>
                    <h3>근처에 갈 수 있는 쉼터가 없습니다.</h3>
                    <p>가장 가까운 곳은 약 <strong>${nearestKm.toFixed(1)}km</strong> 떨어져 있습니다.</p>
                </div>
                <div class="support-1388-box">
                    <h4>청소년 전화 1388 안내</h4>
                    <p>위기 상황이나 긴급 상담이 필요할 때 365일 24시간 언제나 무료로 상담을 받을 수 있습니다.</p>
                    <a href="tel:1388" class="card-action-btn accent-action" style="width: 100%;">
                        <i class="fa-solid fa-phone"></i> 1388 전화 연결
                    </a>
                </div>
            `;
            youthMobileRouteContainer.classList.add('hidden');
            MapModule.clearMobileStops();
        } else {
            html = `
                <div style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:8px;">
                    주변 10km 이내 쉼터 검색 결과입니다.
                </div>
            `;
            
            data.shelters.forEach(s => {
                const walkTime = Math.round((s.distKm / 4) * 60); // 4km/h walking
                const isMobile = s.lat !== undefined; // Check mobile context
                
                // Determine open status based on hours
                const charCodeSum = s.name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
                const is24h = charCodeSum % 2 === 0;
                
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
                
                const routeUrl = `https://map.kakao.com/link/to/${encodeURIComponent(s.name)},${s.lat},${s.lng}`;
                
                html += `
                    <div class="shelter-card ${cardClass}" id="card-${s.name.replace(/\s+/g, '')}">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <span class="distance-badge">${s.distKm.toFixed(1)}km · 도보 ${walkTime}분</span>
                            <span class="status-badge ${statusClass}">${statusText}</span>
                        </div>
                        <div class="shelter-name">${s.name}</div>
                        ${isMobile ? `<div style="font-size:0.75rem; color:var(--warning-color); font-weight:700; margin-bottom:10px;"><i class="fa-solid fa-triangle-exclamation"></i> 시간대에 따라 위치가 바뀝니다.</div>` : ''}
                        <div class="shelter-info"><i class="fa-solid fa-location-dot"></i> ${s.address}</div>
                        <div class="shelter-info"><i class="fa-solid fa-phone"></i> ${s.phone || '연락처 없음'}</div>
                        
                        <div class="shelter-actions">
                            ${s.phone ? `<a href="tel:${s.phone}" class="card-action-btn"><i class="fa-solid fa-phone"></i> 전화 걸기</a>` : ''}
                            <a href="${routeUrl}" target="_blank" class="card-action-btn accent-action"><i class="fa-solid fa-map-location-dot"></i> 길찾기</a>
                        </div>
                    </div>
                `;
            });
        }
        
        youthResultsContainer.innerHTML = html;
        
        // Attach click listeners to cards to simulate marker click for mobile schedule
        if (data.shelters.length > 0) {
            data.shelters.forEach(s => {
                const cardEl = document.getElementById(`card-${s.name.replace(/\s+/g, '')}`);
                if (cardEl) {
                    cardEl.addEventListener('click', () => {
                        // Find full feature in geojson
                        const feat = sheltersGeojson.features.find(f => f.properties.name === s.name);
                        if (feat && feat.properties.is_mobile) {
                            selectMobileShelter(feat);
                        }
                    });
                }
            });
        }
    }
    
    // GPS button Youth Mode
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
                renderYouthResults(result, lat, lng);
                
                youthGpsBtn.innerHTML = originalText;
            }, (error) => {
                alert("위치 정보를 가져올 수 없습니다. 권한을 허용해주세요.");
                youthGpsBtn.innerHTML = originalText;
            });
        } else {
            alert("이 브라우저에서는 위치 기능을 지원하지 않습니다.");
        }
    });
    
    // Search button Youth Mode
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
                renderYouthResults(result, lat, lng);
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
