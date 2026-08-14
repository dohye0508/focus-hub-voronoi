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
    let mobileRoutesData = null;
    let currentMode = 'start'; // 'start', 'youth', 'admin'
    
    let activeRoute = null; // Current selected mobile route
    let activeDay = null;   // Current active day filter (e.g. 'MON')
    
    // Init Map
    MapModule.init();
    
    // Fetch Data
    try {
        const [cellsRes, sheltersRes, routesRes] = await Promise.all([
            fetch('public/data/cells.json'),
            fetch('public/data/shelters.json'),
            fetch('public/data/mobile_routes.json')
        ]);
        
        cellsGeojson = await cellsRes.json();
        sheltersGeojson = await sheltersRes.json();
        mobileRoutesData = await routesRes.json();
        
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
        
        // Update everyday stats (rounded)
        metricCoverage.innerHTML = `<strong>${result.newCoverage.toFixed(1)}%</strong>`;
        metricMaxDist.innerHTML = `<strong>${Math.round(result.maxDistance)}km</strong>`;
        metricUncoveredCount.innerHTML = `<strong>${result.uncoveredCount}곳</strong>`;
        metricUncoveredNames.innerText = result.topUncoveredRegions.join(', ');
        
        // Calculate Extremes Comparison
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
            MapModule.showCells(); // Show analytical view
            
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
    
    function checkIsNowHere(arrive, depart, stopDays) {
        const now = new Date();
        const day = now.getDay(); // 0 is Sunday, 1 is Monday...
        const hour = now.getHours();
        const minute = now.getMinutes();
        const nowMin = hour * 60 + minute;
        
        const [aH, aM] = arrive.split(':').map(Number);
        const arrMin = aH * 60 + aM;
        const [dH, dM] = depart.split(':').map(Number);
        let depMin = dH * 60 + dM;
        
        const dayNames = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
        const todayName = dayNames[day];
        const yesterdayName = dayNames[day === 0 ? 6 : day - 1];
        
        if (depMin < arrMin) {
            // Crosses midnight
            if (nowMin < depMin && stopDays.includes(yesterdayName)) {
                return true;
            }
            if (nowMin >= arrMin && stopDays.includes(todayName)) {
                return true;
            }
        } else {
            if (nowMin >= arrMin && nowMin < depMin && stopDays.includes(todayName)) {
                return true;
            }
        }
        return false;
    }
    
    function selectMobileRoute(shelterName) {
        if (!mobileRoutesData) return;
        const route = mobileRoutesData.shelters.find(r => r.shelter_name === shelterName);
        if (!route) return;
        
        activeRoute = route;
        
        // Default day filter to today
        const now = new Date();
        const engDays = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
        activeDay = engDays[now.getDay()];
        
        // If today is Sunday (SUN) and not operating on SUN, show first operating day or just SUN
        if (!route.operating_days.includes(activeDay) && route.operating_days.length > 0) {
            // Default to first operating day instead of showing empty initially, or just keep Sunday to let them see empty message
        }
        
        const feat = sheltersGeojson.features.find(f => f.properties.name === shelterName);
        const phone = feat ? feat.properties.phone : '';
        
        updateRouteUI(phone);
    }
    
    function updateRouteUI(phone) {
        const route = activeRoute;
        if (!route) return;
        
        const isDummy = route.is_dummy === true;
        
        let html = '';
        
        // 1. Disclaimer Banner
        if (isDummy) {
            html += `
                <div class="disclaimer-banner">
                    <i class="fa-solid fa-circle-info"></i>
                    <div>
                        예시 일정입니다. 실제 운행 정보는 해당 기관에 확인하세요.<br>
                        <small>기관 연락처: ${phone || '연락처 없음'}</small>
                    </div>
                </div>
            `;
        }
        
        // 2. Day Filter Buttons
        const engDays = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
        const korDays = ["월", "화", "수", "목", "금", "토", "일"];
        
        html += `
            <div class="day-filter" style="display:flex; gap:6px; margin-bottom:14px; overflow-x:auto; padding-bottom:4px;">
        `;
        engDays.forEach((day, idx) => {
            const isActive = day === activeDay;
            const btnClass = isActive ? "mode-btn active" : "mode-btn";
            html += `
                <button class="${btnClass}" style="flex:1; padding:8px 6px; font-size:0.75rem; font-weight:700;" onclick="window.onDayFilterClick('${day}')">
                    ${korDays[idx]}
                </button>
            `;
        });
        html += `</div>`;
        
        // 3. Filtered stops for activeDay
        const filteredStops = route.stops.filter(stop => stop.days.includes(activeDay));
        
        html += `<div class="stops-list-container" style="display:flex; flex-direction:column; gap:10px;">`;
        
        if (filteredStops.length === 0) {
            html += `
                <div class="empty-state" style="padding:30px 0; font-size:0.8rem;">
                    이 요일에는 운행하지 않습니다.
                </div>
            `;
            MapModule.clearMobileStops();
        } else {
            // Sort stops by order
            filteredStops.sort((a, b) => a.order - b.order);
            
            filteredStops.forEach(stop => {
                const isNowHere = checkIsNowHere(stop.arrive, stop.depart, stop.days);
                stop.isNowHere = isNowHere; // Pass flag to map stops renderer
                
                const cardHighlightStyle = isNowHere ? "style='border-color: #6366f1; background: rgba(99, 102, 241, 0.06);'" : "";
                const nowHereBadge = isNowHere ? "<span class='status-badge open-badge' style='margin-left:8px; font-size:0.65rem;'>지금 여기</span>" : "";
                
                // Format days label: e.g. "월·수·금"
                const daysLabel = stop.days.map(d => {
                    const mapDaysIdx = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].indexOf(d);
                    return ["월", "화", "수", "목", "금", "토", "일"][mapDaysIdx];
                }).join('·');
                
                html += `
                    <div class="shelter-card" ${cardHighlightStyle} style="cursor:pointer; padding:12px 16px;" onclick="window.onStopClick(${stop.lat}, ${stop.lng})">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-weight:700; font-size:0.85rem; color:#fff;">
                                ${stop.order}. ${stop.name} ${nowHereBadge}
                            </span>
                        </div>
                        <div style="font-size:0.75rem; color:var(--text-secondary); margin-top:4px;">
                            운행 요일: ${daysLabel} | 시간: ${stop.arrive} – ${stop.depart}
                        </div>
                    </div>
                `;
            });
            
            // Draw Route & Stops on Map
            MapModule.renderRouteStops(filteredStops);
        }
        
        html += `</div>`;
        
        youthMobileRouteContainer.innerHTML = html;
        youthMobileRouteContainer.classList.remove('hidden');
        youthMobileRouteContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    // Global window mappings for inner HTML event bindings
    window.onDayFilterClick = function(day) {
        activeDay = day;
        const feat = sheltersGeojson.features.find(f => f.properties.name === activeRoute.shelter_name);
        const phone = feat ? feat.properties.phone : '';
        updateRouteUI(phone);
    };
    
    window.onStopClick = function(lat, lng) {
        MapModule.getMap().flyTo([lat, lng], 15);
    };
    
    // Register global click handler to coordinate with Leaflet clicks
    window.onShelterClick = function(feature) {
        if (currentMode === 'youth' && feature.properties.is_mobile) {
            selectMobileRoute(feature.properties.name);
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
                const isMobile = s.is_mobile === true; // Check mobile context
                
                // Determine if there is route data for this shelter
                const hasRoute = mobileRoutesData && mobileRoutesData.shelters.some(r => r.shelter_name === s.name);
                
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
                    <div class="shelter-card ${cardClass}" id="card-${s.name.replace(/\s+/g, '')}" style="cursor:pointer;">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <span class="distance-badge">${s.distKm.toFixed(1)}km · 도보 ${walkTime}분</span>
                            <span class="status-badge ${statusClass}">${statusText}</span>
                        </div>
                        <div class="shelter-name">${s.name}</div>
                        ${isMobile ? `<div style="font-size:0.75rem; color:var(--warning-color); font-weight:700; margin-bottom:10px;"><i class="fa-solid fa-triangle-exclamation"></i> 시간대에 따라 위치가 바뀝니다.</div>` : ''}
                        <div class="shelter-info"><i class="fa-solid fa-location-dot"></i> ${s.address}</div>
                        <div class="shelter-info"><i class="fa-solid fa-phone"></i> ${s.phone || '연락처 없음'}</div>
                        
                        <div class="shelter-actions">
                            ${s.phone ? `<a href="tel:${s.phone}" class="card-action-btn" onclick="event.stopPropagation();"><i class="fa-solid fa-phone"></i> 전화</a>` : ''}
                            <a href="${routeUrl}" target="_blank" class="card-action-btn accent-action" onclick="event.stopPropagation();"><i class="fa-solid fa-map-location-dot"></i> 길찾기</a>
                            ${hasRoute ? `<button class="card-action-btn route-view-btn" data-name="${s.name}" onclick="event.stopPropagation(); window.onRouteViewClick('${s.name}')"><i class="fa-solid fa-route"></i> 노선 보기</button>` : ''}
                        </div>
                    </div>
                `;
            });
        }
        
        youthResultsContainer.innerHTML = html;
        
        // Attach click listeners to cards to pan to shelter marker
        if (data.shelters.length > 0) {
            data.shelters.forEach(s => {
                const cardEl = document.getElementById(`card-${s.name.replace(/\s+/g, '')}`);
                if (cardEl) {
                    cardEl.addEventListener('click', () => {
                        MapModule.getMap().flyTo([s.lat, s.lng], 14);
                        // Also auto-select route if mobile
                        const feat = sheltersGeojson.features.find(f => f.properties.name === s.name);
                        if (feat && feat.properties.is_mobile) {
                            selectMobileRoute(s.name);
                        }
                    });
                }
            });
        }
    }
    
    // Action handler for "노선 보기" button click
    window.onRouteViewClick = function(name) {
        selectMobileRoute(name);
    };
    
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
