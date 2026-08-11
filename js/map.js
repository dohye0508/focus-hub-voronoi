const MapModule = (function() {
    let map;
    let cellsLayerGroup;
    let sheltersLayerGroup;
    let optLayerGroup;
    let cellsData = [];
    
    // HSL Color logic based on CVI
    function cviToColor(cvi) {
        // High CVI -> Red (hue 0), Low CVI -> Blue (hue 220)
        const hue = 220 - (cvi * 220);
        return `hsl(${hue}, 80%, 55%)`;
    }

    function initMap() {
        map = L.map('map', {
            center: [36.5, 127.8],
            zoom: 7,
            zoomControl: false // We can add it custom or hide it for mobile feel
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
    }

    function renderCells(geojson) {
        cellsData = geojson.features;
        cellsLayerGroup.clearLayers();

        L.geoJSON(geojson, {
            style: function(feature) {
                return {
                    color: 'rgba(255,255,255,0.1)',
                    weight: 1,
                    fillColor: cviToColor(feature.properties.cvi),
                    fillOpacity: 0.4
                };
            },
            onEachFeature: function(feature, layer) {
                const p = feature.properties;
                const tooltipContent = `
                    <div style="font-family:'Pretendard';">
                        <b>${p.region}</b><br>
                        필요 확률 (CVI): ${(p.cvi * 100).toFixed(1)}%<br>
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
        
        const customIcon = L.divIcon({
            html: '<div style="width:12px;height:12px;background:#10b981;border-radius:50%;border:2px solid #0f172a;box-shadow:0 0 10px rgba(16, 185, 129, 0.6);"></div>',
            iconSize: [12, 12],
            className: 'shelter-icon'
        });

        L.geoJSON(geojson, {
            pointToLayer: function(feature, latlng) {
                // 2km coverage circle (approx 30 mins walk)
                L.circle(latlng, {
                    radius: 2000,
                    color: '#10b981',
                    fillColor: '#10b981',
                    fillOpacity: 0.05,
                    weight: 1,
                    dashArray: '4'
                }).addTo(sheltersLayerGroup);
                
                return L.marker(latlng, {icon: customIcon});
            },
            onEachFeature: function(feature, layer) {
                layer.bindTooltip(`<b>${feature.properties.name}</b>`);
            }
        }).addTo(sheltersLayerGroup);
    }

    function renderOptimizedSites(centers, cellsData, existingShelters) {
        optLayerGroup.clearLayers();
        
        const starIcon = L.divIcon({
            html: '<div style="width:24px;height:24px;background:#f59e0b;border-radius:50%;border:2px solid #fff;display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px;box-shadow:0 0 15px rgba(245, 158, 11, 0.8);"><i class="fa-solid fa-star"></i></div>',
            iconSize: [24, 24],
            className: 'opt-icon'
        });

        // 1. Draw connecting lines (Spider web) from cells to nearest centers
        if (cellsData) {
            cellsData.forEach(cell => {
                const pLat = cell.properties.centroid[1];
                const pLng = cell.properties.centroid[0];
                
                let minDist = Infinity;
                let nearestLat = 0;
                let nearestLng = 0;
                
                // Check existing
                if (existingShelters) {
                    existingShelters.forEach(s => {
                        const sLat = s.geometry.coordinates[1];
                        const sLng = s.geometry.coordinates[0];
                        const d = OptModule.calcDistKm(pLat, pLng, sLat, sLng);
                        if (d < minDist) { minDist = d; nearestLat = sLat; nearestLng = sLng; }
                    });
                }
                
                // Check new centers
                centers.forEach(c => {
                    const d = OptModule.calcDistKm(pLat, pLng, c.lat, c.lng);
                    if (d < minDist) { minDist = d; nearestLat = c.lat; nearestLng = c.lng; }
                });
                
                // If it is covered (e.g. within 5km for visual clarity), draw a faint line
                if (minDist <= 5.0) {
                    L.polyline([[pLat, pLng], [nearestLat, nearestLng]], {
                        color: 'rgba(255, 255, 255, 0.15)',
                        weight: 1,
                        dashArray: '2, 4'
                    }).addTo(optLayerGroup);
                }
            });
        }

        // 2. Draw new centers and their coverage circles
        centers.forEach(c => {
            // Coverage circle
            L.circle([c.lat, c.lng], {
                radius: 2000, // 2km
                color: '#f59e0b',
                fillColor: '#f59e0b',
                fillOpacity: 0.1,
                weight: 1,
                dashArray: '4'
            }).addTo(optLayerGroup);
            
            // Marker
            L.marker([c.lat, c.lng], {icon: starIcon, zIndexOffset: 1000})
             .bindTooltip('<b>새로운 이동형 쉼터 추천 위치</b>')
             .addTo(optLayerGroup);
        });
    }

    return {
        init: initMap,
        renderCells,
        renderShelters,
        renderOptimizedSites,
        getMap: () => map
    };
})();
