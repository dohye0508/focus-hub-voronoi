import geopandas as gpd
import pandas as pd
import folium
from folium.plugins import HeatMap
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from scipy.spatial import Voronoi
import numpy as np
import re
import warnings
warnings.filterwarnings('ignore')

def clean_address(addr):
    if not isinstance(addr, str):
        return ""
    addr = re.sub(r'\(.*?\)', '', addr)
    addr = addr.split(',')[0]
    return addr.strip()

print("1. Loading and filtering data...")
# Load Shelter Data
gdf_shelter = gpd.read_file("data/spatial/전국+청소년쉼터+현황/Youth shelter.shp")
incheon_shelters = gdf_shelter[gdf_shelter['A6'] == '인천'].copy()

# Load Academy Data
df_academies = pd.read_csv("data/processed/academies_merged.csv")
yeonsu_academies = df_academies[df_academies['지역'].str.contains('연수구', na=False)].copy()

# Geocode a subset (Increasing to 100 for a better looking Voronoi)
sample_size = 100
pilot_academies = yeonsu_academies.head(sample_size).copy()

geolocator = Nominatim(user_agent="focus-hub-voronoi-advanced")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

print(f"2. Geocoding {sample_size} academies... (please wait)")
pilot_academies['clean_address'] = pilot_academies['주소'].apply(clean_address)
pilot_academies['location'] = pilot_academies['clean_address'].apply(geocode)
pilot_academies['lat'] = pilot_academies['location'].apply(lambda loc: loc.latitude if loc else None)
pilot_academies['lon'] = pilot_academies['location'].apply(lambda loc: loc.longitude if loc else None)

pilot_academies = pilot_academies.dropna(subset=['lat', 'lon'])
print(f"Successfully geocoded {len(pilot_academies)} academies.")

# 3. Voronoi Calculation
print("3. Generating Voronoi Diagram...")
points = np.array(list(zip(pilot_academies['lon'], pilot_academies['lat'])))

# Add dummy points far away to close the outer Voronoi cells
center_lon, center_lat = points.mean(axis=0)
dummy_points = np.array([
    [center_lon - 0.1, center_lat - 0.1],
    [center_lon - 0.1, center_lat + 0.1],
    [center_lon + 0.1, center_lat - 0.1],
    [center_lon + 0.1, center_lat + 0.1],
])
points_with_dummy = np.vstack([points, dummy_points])
vor = Voronoi(points_with_dummy)

# 4. Visualization
m = folium.Map(location=[center_lat, center_lon], zoom_start=14)

# Plot Voronoi Polygons
for region_index in vor.point_region[:-4]: # exclude dummy points
    region = vor.regions[region_index]
    if not -1 in region and len(region) > 0:
        polygon = [vor.vertices[i] for i in region]
        # Folium expects [lat, lon]
        folium_poly = [[p[1], p[0]] for p in polygon]
        folium.Polygon(
            locations=folium_poly,
            color='blue',
            fill=True,
            fill_opacity=0.1,
            weight=1
        ).add_to(m)

# Add HeatMap
heat_data = [[row['lat'], row['lon']] for index, row in pilot_academies.iterrows()]
HeatMap(heat_data, name="Academy Density", radius=15).add_to(m)

# Add Academy Markers (Small dots)
for index, row in pilot_academies.iterrows():
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=2,
        color='black',
        fill=True,
        popup=row['학원명']
    ).add_to(m)

# Add Shelters as Big Red Markers
for idx, row in incheon_shelters.iterrows():
    folium.Marker(
        location=[float(row['A1']), float(row['A0'])],
        popup=f"Shelter: {row['A9']}",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)

# Save Map
output_path = "results/yeonsu_advanced_analysis.html"
m.save(output_path)
print(f"Advanced analysis map saved to {output_path}")
