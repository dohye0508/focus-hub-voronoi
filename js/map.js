const MapModule = (function() {
    let map;
    let cellsLayerGroup;
    let sheltersLayerGroup;
    let optLayerGroup;
    let mobileStopsLayerGroup; // Layer group for mobile route stops
    let cellsData = [];
    
    // HSL Color logic based on CVI
    function cviToColor(cvi) {
        // High CVI -> Red (hue 0), Low CVI -> Blue (hue 220)
        const hue = 220 - (cvi * 220);
        return `hsl(${hue}, 80%, 55%)`;
    }

    function initMap() {
        map = L.map('map', {
            center: [36.2, 127.8],
            zoom: 7.5,
            zoomControl: false
        });

        // Dark mode tile layer (CartoDB Dark Matter)
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }).addTo(map);

        cellsLayerGroup = L.layerGroup().addTo(map);
        sheltersLayerGroup = L.layerGroup().addTo(map);
        optLayerGroup = L.layerGroup().addTo(map);
        mobileStopsLayerGroup = L.layerGroup().addTo(map);
    }

    function renderCells(geojson) {
        cellsData = geojson.features;
        cellsLayerGroup.clearLayers();

        L.geoJSON(geojson, {
            style: function(feature) {
                return {
                    color: 'rgba(255,255,255,0.06)',
                    weight: 1,
                    fillColor: cviToColor(feature.properties.cvi),
                    fillOpacity: 0.35
                };
            },
            onEachFeature: function(feature, layer) {
                const p = feature.properties;
                const tooltipContent = `
                    <div style="font-family:'Pretendard';">
                        <b>${p.region}</b><br>
                        취약 수준: ${(p.cvi * 100).toFixed(0)}%<br>
                        청소년 인구: ${p.population.toLocaleString()}명
                    </div>
                `;
                layer.bindTooltip(tooltipContent, {
                    className: 'custom-tooltip',
                    sticky: true
                });
            }
        }).addTo(cellsLayerGroup);
    }

    function renderShelters(geojson) {
        sheltersLayerGroup.clearLayers();

        L.geoJSON(geojson, {
            pointToLayer: function(feature, latlng) {
                const isMobile = feature.properties.is_mobile === true;
                
                // 2km coverage circle (approx 30 mins walk)
                L.circle(latlng, {
                    radius: 2000,
                    color: isMobile ? '#f59e0b' : '#10b981',
                    fillColor: isMobile ? '#f59e0b' : '#10b981',
                    fillOpacity: 0.04,
                    weight: 1,
                    dashArray: '3, 5'
                }).addTo(sheltersLayerGroup);
                
                const customIcon = L.divIcon({
                    html: isMobile 
                        ? '<div style="width:14px;height:14px;background:#f59e0b;border-radius:50%;border:2px solid #0f172a;box-shadow:0 0 10px rgba(245, 158, 11, 0.7);display:flex;align-items:center;justify-content:center;color:#fff;font-size:8px;"><i class="fa-solid fa-bus"></i></div>'
                        : '<div style="width:12px;height:12px;background:#10b981;border-radius:50%;border:2px solid #0f172a;box-shadow:0 0 10px rgba(16, 185, 129, 0.6);"></div>',
                    iconSize: isMobile ? [14, 14] : [12, 12],
                    className: 'shelter-icon'
                });
                
                return L.marker(latlng, {icon: customIcon});
            },
            onEachFeature: function(feature, layer) {
                const typeText = feature.properties.is_mobile ? '이동형 쉼터' : '고정형 쉼터';
                layer.bindTooltip(`<b>${feature.properties.name}</b> (${typeText})`);
                
                layer.on('click', function() {
                    if (window.onShelterClick) {
                        window.onShelterClick(feature);
                    }
                });
            }
        }).addTo(sheltersLayerGroup);
    }

    function renderRouteStops(stops) {
        mobileStopsLayerGroup.clearLayers();
        if (!stops || stops.length === 0) return;
        
        const latlngs = [];
        
        stops.forEach((stop) => {
            const latlng = [stop.lat, stop.lng];
            latlngs.push(latlng);
            
            const isNowHere = stop.isNowHere === true;
            
            const numIcon = L.divIcon({
                html: `<div style="width:${isNowHere ? 22 : 16}px;height:${isNowHere ? 22 : 16}px;background:${isNowHere ? '#6366f1' : '#475569'};border-radius:50%;border:2px solid #fff;box-shadow:0 0 10px rgba(99,102,241,0.6);display:flex;align-items:center;justify-content:center;color:#fff;font-size:${isNowHere ? 10 : 8}px;font-weight:700;">${stop.order}</div>`,
                iconSize: isNowHere ? [22, 22] : [16, 16],
                className: 'mobile-stop-marker'
            });
            
            L.marker(latlng, {icon: numIcon})
                .bindTooltip(`<b>${stop.order}. ${stop.name}</b><br>운행일: ${stop.days.join(', ')}<br>시간: ${stop.arrive} ~ ${stop.depart}${isNowHere ? ' <b style="color:#a5b4fc;">[지금 여기]</b>' : ''}`)
                .addTo(mobileStopsLayerGroup);
        });
        
        // Draw polyline connecting stops
        if (latlngs.length > 1) {
            L.polyline(latlngs, {
                color: '#6366f1',
                weight: 3,
                opacity: 0.85,
                dashArray: '4, 6'
            }).addTo(mobileStopsLayerGroup);
        }
        
        // Fit map bounds to show route
        if (latlngs.length > 0) {
            const bounds = L.latLngBounds(latlngs);
            map.fitBounds(bounds, {padding: [50, 50]});
        }
    }

    function clearMobileStops() {
        mobileStopsLayerGroup.clearLayers();
    }

    function renderOptimizedSites(centers, cellsData, existingShelters) {
        optLayerGroup.clearLayers();
        
        const starIcon = L.divIcon({
            html: '<div style="width:24px;height:24px;background:#6366f1;border-radius:50%;border:2px solid #fff;display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;box-shadow:0 0 15px rgba(99, 102, 241, 0.8);"><i class="fa-solid fa-star"></i></div>',
            iconSize: [24, 24],
            className: 'opt-icon'
        });

        // 1. Draw lines to closest centers/shelters
        if (cellsData) {
            cellsData.forEach(cell => {
                const pLat = cell.properties.centroid[1];
                const pLng = cell.properties.centroid[0];
                
                let minDist = Infinity;
                let nearestLat = 0;
                let nearestLng = 0;
                
                if (existingShelters) {
                    existingShelters.forEach(s => {
                        const sLat = s.geometry.coordinates[1];
                        const sLng = s.geometry.coordinates[0];
                        const d = OptModule.calcDistKm(pLat, pLng, sLat, sLng);
                        if (d < minDist) { minDist = d; nearestLat = sLat; nearestLng = sLng; }
                    });
                }
                
                centers.forEach(c => {
                    const d = OptModule.calcDistKm(pLat, pLng, c.lat, c.lng);
                    if (d < minDist) { minDist = d; nearestLat = c.lat; nearestLng = c.lng; }
                });
                
                if (minDist <= 5.0) {
                    L.polyline([[pLat, pLng], [nearestLat, nearestLng]], {
                        color: 'rgba(255, 255, 255, 0.08)',
                        weight: 1,
                        dashArray: '2, 4'
                    }).addTo(optLayerGroup);
                }
            });
        }

        // 2. Draw new centers
        centers.forEach(c => {
            L.circle([c.lat, c.lng], {
                radius: 2000, // 2km
                color: '#6366f1',
                fillColor: '#6366f1',
                fillOpacity: 0.08,
                weight: 1,
                dashArray: '4'
            }).addTo(optLayerGroup);
            
            const regionsList = c.assignedCells.map(cell => cell.region).slice(0, 4).join(', ') + (c.assignedCells.length > 4 ? ' 등' : '');
            
            const popupContent = `
                <div style="font-family:'Pretendard'; font-size:0.85rem; line-height:1.4; color:#334155; width:220px;">
                    <b style="font-size:0.95rem; color:#6366f1;">이동형 쉼터 버스 추천 위치</b><br>
                    <div style="margin-top:6px; border-top:1px solid #e2e8f0; padding-top:6px;">
                        <b>담당 지역 청소년 수:</b> ${c.totalPopulation.toLocaleString()}명<br>
                        <b>주요 담당 범위:</b> ${regionsList || '없음'} (${c.assignedCells.length}개 행정구역)
                    </div>
                </div>
            `;
            
            L.marker([c.lat, c.lng], {icon: starIcon, zIndexOffset: 1000})
             .bindPopup(popupContent)
             .addTo(optLayerGroup);
        });
    }

    return {
        init: initMap,
        renderCells,
        renderShelters,
        renderRouteStops,
        clearMobileStops,
        renderOptimizedSites,
        showCells: () => { if(map && cellsLayerGroup) map.addLayer(cellsLayerGroup); },
        hideCells: () => { if(map && cellsLayerGroup) map.removeLayer(cellsLayerGroup); },
        getMap: () => map
    };
})();
