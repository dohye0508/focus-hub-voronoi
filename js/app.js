document.addEventListener('DOMContentLoaded', async () => {
    
    // UI Elements
    const pSlider = document.getElementById('p-slider');
    const pVal = document.getElementById('p-val');
    const lambdaSlider = document.getElementById('lambda-slider');
    const lambdaText = document.getElementById('lambda-text');
    
    const coverageProgress = document.getElementById('coverage-progress');
    const coverageBadge = document.getElementById('coverage-badge');
    const coverageText = document.getElementById('coverage-text');
    
    const gpsBtn = document.getElementById('gps-btn');
    const modalClose = document.getElementById('close-modal');
    const modalOverlay = document.getElementById('gps-modal');
    
    // State
    let cellsGeojson = null;
    let sheltersGeojson = null;
    
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
        
        // Initial run
        runOpt();
        
    } catch (e) {
        console.error("Failed to load data:", e);
        coverageText.innerHTML = "<span style='color:red;'>데이터 로드 실패</span>";
    }
    
    function runOpt() {
        if(!cellsGeojson || !sheltersGeojson) return;
        
        const p = parseInt(pSlider.value);
        const lambda = parseFloat(lambdaSlider.value);
        
        const result = OptModule.runOptimization(
            cellsGeojson.features,
            sheltersGeojson.features,
            p,
            lambda
        );
        
        MapModule.renderOptimizedSites(result.centers, cellsGeojson.features, sheltersGeojson.features);
        
        // Update Dashboard
        coverageProgress.style.width = `${result.newCoverage}%`;
        coverageBadge.innerText = `${result.newCoverage.toFixed(1)}% 커버`;
        
        coverageText.innerHTML = `이동형 쉼터 <b>${p}개</b>를 추가하면 청소년 커버리지가 <br><b>${result.baseCoverage.toFixed(1)}%</b>에서 <b>${result.newCoverage.toFixed(1)}%</b>로 오릅니다.`;
    }
    
    // Event Listeners
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
    
    // GPS
    gpsBtn.addEventListener('click', () => {
        if(!cellsGeojson || !sheltersGeojson) return;
        GeoModule.locate(cellsGeojson.features, sheltersGeojson.features);
    });
    
    // Search
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
});
