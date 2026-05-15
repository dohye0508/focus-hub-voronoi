import geopandas as gpd
import pandas as pd
import folium
from folium.plugins import HeatMap
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# 1. Load Shelter Data (Incheon only)
gdf_shelter = gpd.read_file("전국+청소년쉼터+현황/Youth shelter.shp")
# A0: Long, A1: Lat, A6: City
incheon_shelters = gdf_shelter[gdf_shelter['A6'] == '인천'].copy()
print(f"Found {len(incheon_shelters)} shelters in Incheon.")

# 2. Load Academy Data (Yeonsu-gu only)
df_academies = pd.read_csv("academies_merged.csv")
# Handle potential encoding/naming issues in '지역'
yeonsu_academies = df_academies[df_academies['지역'].str.contains('연수구', na=False)].copy()
print(f"Found {len(yeonsu_academies)} academies in Yeonsu-gu.")

# 3. Geocoding Pilot (Sample 50 academies to show demo quickly)
sample_size = 50
pilot_academies = yeonsu_academies.head(sample_size).copy()

geolocator = Nominatim(user_agent="focus-hub-voronoi-analysis")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

import re

def clean_address(addr):
    if not isinstance(addr, str):
        return ""
    # Remove text in parentheses
    addr = re.sub(r'\(.*?\)', '', addr)
    # Remove building details after comma
    addr = addr.split(',')[0]
    return addr.strip()

print(f"Geocoding {sample_size} academies (this will take ~1 min)...")
pilot_academies['clean_address'] = pilot_academies['주소'].apply(clean_address)
pilot_academies['location'] = pilot_academies['clean_address'].apply(geocode)
pilot_academies['lat'] = pilot_academies['location'].apply(lambda loc: loc.latitude if loc else None)
pilot_academies['lon'] = pilot_academies['location'].apply(lambda loc: loc.longitude if loc else None)

# Drop those that couldn't be geocoded
pilot_academies = pilot_academies.dropna(subset=['lat', 'lon'])
print(f"Successfully geocoded {len(pilot_academies)} academies.")

# 4. Visualization
m = folium.Map(location=[37.41, 126.68], zoom_start=13) # Focused on Yeonsu-gu/Songdo

# Add HeatMap for Academies
heat_data = [[row['lat'], row['lon']] for index, row in pilot_academies.iterrows()]
HeatMap(heat_data, name="Academy Density").add_to(m)

# Add Shelters as Markers
for idx, row in incheon_shelters.iterrows():
    # A0 is Long, A1 is Lat
    folium.Marker(
        location=[float(row['A1']), float(row['A0'])],
        popup=f"Shelter: {row['A9']}",
        icon=folium.Icon(color='red', icon='info-sign')
    ).add_to(m)

# Save Map
m.save("yeonsu_pilot_analysis.html")
print("Analysis map saved to yeonsu_pilot_analysis.html")
