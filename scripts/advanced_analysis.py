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

# Geocode a larger subset for a better looking Voronoi
sample_size = 300
pilot_academies = yeonsu_academies.head(sample_size).copy()

geolocator = Nominatim(user_agent="focus-hub-voronoi-advanced-v2")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

print(f"2. Geocoding {sample_size} academies... (This will take a few minutes)")
pilot_academies['clean_address'] = pilot_academies['주소'].apply(clean_address)
pilot_academies['location'] = pilot_academies['clean_address'].apply(geocode)
pilot_academies['lat'] = pilot_academies['location'].apply(lambda loc: loc.latitude if loc else None)
pilot_academies['lon'] = pilot_academies['location'].apply(lambda loc: loc.longitude if loc else None)

pilot_academies = pilot_academies.dropna(subset=['lat', 'lon'])

# Add jitter to handle academies at the same address
print("   Adding jitter to overlapping points...")
pilot_academies['lat'] += np.random.uniform(-0.0002, 0.0002, size=len(pilot_academies))
pilot_academies['lon'] += np.random.uniform(-0.0002, 0.0002, size=len(pilot_academies))

print(f"Successfully geocoded and processed {len(pilot_academies)} academies.")

# 3. Voronoi Calculation with clipping
print("3. Generating Voronoi Diagram with clipping...")
points = np.array(list(zip(pilot_academies['lon'], pilot_academies['lat'])))

# Improved clipping: add a bounding box of points
lat_min, lat_max = points[:, 1].min() - 0.02, points[:, 1].max() + 0.02
lon_min, lon_max = points[:, 0].min() - 0.02, points[:, 0].max() + 0.02
boundary_points = np.array([
    [lon_min, lat_min], [lon_min, lat_max], [lon_max, lat_min], [lon_max, lat_max],
    [(lon_min+lon_max)/2, lat_min], [(lon_min+lon_max)/2, lat_max],
    [lon_min, (lat_min+lat_max)/2], [lon_max, (lat_min+lat_max)/2]
])
points_to_vor = np.vstack([points, boundary_points])
vor = Voronoi(points_to_vor)

# 4. Visualization
m = folium.Map(location=[points[:, 1].mean(), points[:, 0].mean()], zoom_start=14)

# Plot Voronoi Polygons (All cells)
for region_index in vor.point_region[:len(points)]: # only for real points
    region = vor.regions[region_index]
    if not -1 in region and len(region) > 0:
        polygon = [vor.vertices[i] for i in region]
        folium_poly = [[p[1], p[0]] for p in polygon]
        folium.Polygon(
            locations=folium_poly,
            color='blue',
            fill=True,
            fill_opacity=0.15,
            weight=0.5,
            popup="Catchment Area"
        ).add_to(m)

# Add HeatMap
heat_data = [[row['lat'], row['lon']] for index, row in pilot_academies.iterrows()]
HeatMap(heat_data, name="Academy Density", radius=10, blur=15).add_to(m)

# Add Academy Markers
for index, row in pilot_academies.iterrows():
    folium.CircleMarker(
        location=[row['lat'], row['lon']],
        radius=4,
        color='black',
        fill=True,
        fill_color='white',
        fill_opacity=1,
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
