const OptModule = (function() {
    
    // Calculate distance in km between two lat/lng points using Haversine
    function calcDistKm(lat1, lon1, lat2, lon2) {
        const R = 6371; // km
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                  Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }

    // Simple k-means clustering in JS (Weighted by CVI * Population)
    function kMeansWeighted(points, k, iterations=10) {
        if(points.length === 0 || k <= 0) return [];
        if(k >= points.length) return points.map(p => ({lat: p.lat, lng: p.lng}));
        
        // Randomly initialize k centers from points
        let centers = [];
        let used = new Set();
        while(centers.length < k) {
            let idx = Math.floor(Math.random() * points.length);
            if(!used.has(idx)) {
                used.add(idx);
                centers.push({lat: points[idx].lat, lng: points[idx].lng});
            }
        }
        
        for(let iter = 0; iter < iterations; iter++) {
            let clusters = Array(k).fill().map(() => []);
            
            // Assign points to nearest center
            points.forEach(p => {
                let minDist = Infinity;
                let minIdx = -1;
                centers.forEach((c, idx) => {
                    let d = calcDistKm(p.lat, p.lng, c.lat, c.lng);
                    if(d < minDist) { minDist = d; minIdx = idx; }
                });
                clusters[minIdx].push(p);
            });
            
            // Recompute centers weighted by demand (cvi * population)
            let newCenters = [];
            for(let i=0; i<k; i++) {
                if(clusters[i].length === 0) {
                    newCenters.push(centers[i]);
                    continue;
                }
                
                let sumWeight = 0;
                let sumLat = 0;
                let sumLng = 0;
                
                clusters[i].forEach(p => {
                    // Demand = probability * population
                    let weight = p.cvi * p.population; 
                    if (weight < 0.0001) weight = 0.0001; // prevent zero division
                    
                    sumWeight += weight;
                    sumLat += p.lat * weight;
                    sumLng += p.lng * weight;
                });
                
                newCenters.push({
                    lat: sumLat / sumWeight,
                    lng: sumLng / sumWeight
                });
            }
            centers = newCenters;
        }
        return centers;
    }

    // Local Search for Equity (Lambda)
    // J(λ) = (1 − λ) * 가중평균거리 + λ * 최대거리
    function applyEquity(points, centers, lambda, iterations=5) {
        if(lambda === 0) return centers; // Pure efficiency
        
        // Simple heuristic: Move centers slightly towards the point with the maximum distance
        let currentCenters = JSON.parse(JSON.stringify(centers)); // deep copy
        
        for(let iter=0; iter<iterations; iter++) {
            let maxDist = 0;
            let worstPoint = null;
            let worstCenterIdx = -1;
            
            points.forEach(p => {
                let minDist = Infinity;
                let cIdx = -1;
                currentCenters.forEach((c, idx) => {
                    let d = calcDistKm(p.lat, p.lng, c.lat, c.lng);
                    if(d < minDist) { minDist = d; cIdx = idx; }
                });
                if(minDist > maxDist) {
                    maxDist = minDist;
                    worstPoint = p;
                    worstCenterIdx = cIdx;
                }
            });
            
            if(worstPoint && worstCenterIdx !== -1) {
                // Shift the responsible center towards the worst point based on lambda
                // The higher the lambda, the bigger the shift
                const shiftRate = lambda * 0.2; // dampen to prevent crazy jumping
                currentCenters[worstCenterIdx].lat += (worstPoint.lat - currentCenters[worstCenterIdx].lat) * shiftRate;
                currentCenters[worstCenterIdx].lng += (worstPoint.lng - currentCenters[worstCenterIdx].lng) * shiftRate;
            }
        }
        
        return currentCenters;
    }

    function calculateCoverage(points, centers, existingShelters) {
        let coveredPop = 0;
        let totalPop = 0;
        
        points.forEach(p => {
            totalPop += p.population;
            
            let minDist = Infinity;
            // Check existing shelters
            existingShelters.forEach(s => {
                let d = calcDistKm(p.lat, p.lng, s.lat, s.lng);
                if(d < minDist) minDist = d;
            });
            
            // Check new centers
            centers.forEach(c => {
                let d = calcDistKm(p.lat, p.lng, c.lat, c.lng);
                if(d < minDist) minDist = d;
            });
            
            // 2.0km coverage radius (Walking 30 mins)
            if(minDist <= 2.0) {
                coveredPop += p.population;
            }
        });
        
        return totalPop === 0 ? 0 : (coveredPop / totalPop) * 100;
    }

    return {
        runOptimization: function(cellsData, sheltersData, p, lambda) {
            // Extract points
            const points = cellsData.map(f => ({
                lat: f.properties.centroid[1],
                lng: f.properties.centroid[0],
                cvi: f.properties.cvi,
                population: f.properties.population
            }));
            
            const existingShelters = sheltersData.map(f => ({
                lat: f.geometry.coordinates[1],
                lng: f.geometry.coordinates[0]
            }));
            
            // 1. Initial k-means (efficiency)
            let centers = kMeansWeighted(points, p);
            
            // 2. Local search for equity (lambda)
            centers = applyEquity(points, centers, lambda);
            
            // 3. Calculate Coverage
            let coverage = calculateCoverage(points, centers, existingShelters);
            let baseCoverage = calculateCoverage(points, [], existingShelters);
            
            return {
                centers: centers,
                baseCoverage: baseCoverage,
                newCoverage: coverage
            };
        },
        calcDistKm
    };
})();
