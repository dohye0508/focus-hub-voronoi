const GeoModule = (function() {
    
    function findNearest(lat, lng, cellsData, sheltersData) {
        // Find nearest cell to get local context
        let minDistCell = Infinity;
        let nearestCell = null;
        
        cellsData.forEach(f => {
            const pLat = f.properties.centroid[1];
            const pLng = f.properties.centroid[0];
            const d = OptModule.calcDistKm(lat, lng, pLat, pLng);
            if(d < minDistCell) {
                minDistCell = d;
                nearestCell = f.properties;
            }
        });
        
        // Find shelters within 10km and sort by distance
        let nearbyShelters = [];
        sheltersData.forEach(f => {
            const sLat = f.geometry.coordinates[1];
            const sLng = f.geometry.coordinates[0];
            const d = OptModule.calcDistKm(lat, lng, sLat, sLng);
            if (d <= 10.0) {
                nearbyShelters.push({
                    name: f.properties.name,
                    address: f.properties.address,
                    phone: f.properties.phone,
                    distKm: d,
                    lat: sLat,
                    lng: sLng,
                    is_mobile: f.properties.is_mobile === true
                });
            }
        });
        
        nearbyShelters.sort((a,b) => a.distKm - b.distKm);
        
        // Calculate Percentile (lower is worse)
        // Sort all cells by CVI (highest CVI = worst accessibility = low percentile)
        let sortedCVI = cellsData.map(f => f.properties.cvi).sort((a,b) => a - b);
        let myCvi = nearestCell.cvi;
        // Count how many regions have a lower CVI (are better off)
        let worseCount = sortedCVI.filter(val => val > myCvi).length;
        let percentile = (worseCount / sortedCVI.length) * 100;
        
        return {
            cell: nearestCell,
            shelters: nearbyShelters.slice(0, 3), // Top 3
            percentile: percentile
        };
    }

    function showModal(data) {
        const modal = document.getElementById('gps-modal');
        const body = document.getElementById('modal-body');
        
        let html = '';
        
        if (data.shelters.length === 0) {
            // Nothing within 10km - The powerful message
            html = `
                <div class="danger-box">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <h3>반경 10km 내 쉼터 부재</h3>
                    <p>당신의 주변에는 청소년 쉼터가 단 한 곳도 없습니다.<br>전국 청소년의 34%가 같은 상황입니다.</p>
                </div>
                <div style="margin-top:20px;">
                    <p style="color:#94a3b8; font-size:0.9rem;">
                        현재 지역: <b>${data.cell.region}</b><br>
                        접근성 열악도: 상위 <b>${data.percentile.toFixed(1)}%</b> 수준
                    </p>
                </div>
            `;
        } else {
            // Found shelters
            html = `
                <h3 class="modal-title">가장 가까운 쉼터</h3>
                <p class="modal-desc">현재 지역 <b>${data.cell.region}</b>의 접근성은 전국 상위 <strong>${data.percentile.toFixed(1)}%</strong> 수준으로 파악됩니다.</p>
            `;
            
            data.shelters.forEach(s => {
                const walkTime = Math.round((s.distKm / 4) * 60); // 4km/h walking
                html += `
                    <div class="shelter-card">
                        <div class="distance-badge">${s.distKm.toFixed(1)}km (도보 약 ${walkTime}분)</div>
                        <div class="shelter-name">${s.name}</div>
                        <div class="shelter-info"><i class="fa-solid fa-location-dot"></i> ${s.address}</div>
                        <div class="shelter-info"><i class="fa-solid fa-phone"></i> ${s.phone || '연락처 없음'}</div>
                    </div>
                `;
            });
        }
        
        body.innerHTML = html;
        modal.classList.remove('hidden');
    }

    return {
        locate: function(cellsData, sheltersData) {
            if ("geolocation" in navigator) {
                // Show loading on btn
                const btn = document.getElementById('gps-btn');
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
                
                navigator.geolocation.getCurrentPosition((position) => {
                    const lat = position.coords.latitude;
                    const lng = position.coords.longitude;
                    
                    // Fly to location
                    MapModule.getMap().flyTo([lat, lng], 13);
                    
                    const result = findNearest(lat, lng, cellsData, sheltersData);
                    showModal(result);
                    
                    btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i>';
                }, (error) => {
                    alert("위치 정보를 가져올 수 없습니다. 권한을 허용해주세요.");
                    btn.innerHTML = '<i class="fa-solid fa-location-crosshairs"></i>';
                });
            } else {
                alert("이 브라우저에서는 위치 기능을 지원하지 않습니다.");
            }
        },
        
        searchAddress: async function(query, cellsData, sheltersData) {
            const btn = document.getElementById('search-btn');
            const originalIcon = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
            
            try {
                // Nominatim OSM API
                const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(query)}&format=json&limit=1`;
                const response = await fetch(url);
                const data = await response.json();
                
                if(data && data.length > 0) {
                    const lat = parseFloat(data[0].lat);
                    const lng = parseFloat(data[0].lon);
                    
                    MapModule.getMap().flyTo([lat, lng], 13);
                    const result = findNearest(lat, lng, cellsData, sheltersData);
                    showModal(result);
                } else {
                    alert("주소를 찾을 수 없습니다.");
                }
            } catch(e) {
                console.error(e);
                alert("주소 검색 중 오류가 발생했습니다.");
            }
            
            btn.innerHTML = originalIcon;
        },
        
        findNearest: findNearest
    };
})();
