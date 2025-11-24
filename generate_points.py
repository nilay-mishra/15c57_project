import numpy as np
from shapely.geometry import shape, Point
import matplotlib.pyplot as plt
import requests
import csv
import osmnx as ox

def get_massachusetts_polygon():
    url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/us-states.json"
    print("Downloading boundary data...")
    try:
        response = requests.get(url)
        data = response.json()
        for feature in data['features']:
            if feature['properties']['name'] == 'Massachusetts':
                return shape(feature['geometry'])
        raise ValueError("MA not found.")
    except Exception as e:
        print(f"Error: {e}")
        return None
    
def generate_grid_points(polygon, target_points=150):
    """
    Generates a grid of points that fits the polygon.
    Adjusts for the Earth's curvature to keep spacing visualy equal.
    """
    min_x, min_y, max_x, max_y = polygon.bounds
    lat_correction = np.cos(np.radians((min_y + max_y) / 2))
    width = (max_x - min_x) * lat_correction
    height = max_y - min_y
    estimated_total_grid_points = target_points / 0.5
    aspect_ratio = width / height
    n_y = int(np.sqrt(estimated_total_grid_points / aspect_ratio))
    n_x = int(n_y * aspect_ratio)
    print(f"Creating a grid of {n_x} x {n_y} ({n_x*n_y} candidates)...")
    x_coords = np.linspace(min_x, max_x, n_x)
    y_coords = np.linspace(min_y, max_y, n_y)
    # test if in MA
    valid_points, formatted_strings = [], []
    for y in y_coords:
        for x in x_coords:
            p = Point(x, y)
            if polygon.contains(p):
                valid_points.append([y, x])         
    return valid_points
    
ma_poly = get_massachusetts_polygon()
val_points = generate_grid_points(ma_poly)
with open("possible_facilities.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(val_points)

G = ox.graph_from_place("Massachusetts, USA", network_type="drive")

# Find the nearest actual road node to your random point
nearest_node = ox.distance.nearest_nodes(G, X=-71.0589, Y=42.3601)
node_data = G.nodes[nearest_node]
print(f"Nearest Road Coordinate: {node_data['y']},{node_data['x']}")

plant_locations = []
with open("raw_plant_locations.csv", "r") as f:
    reader = csv.reader(f)
    for row in reader:
        if row[1] == " " or row[2] == " ":
            continue
        latitude = float(row[1])
        longitude = float(row[2])
        loc = Point(longitude, latitude)
        if ma_poly.contains(loc):
            plant_locations.append((latitude, longitude))
with open("cleaned_plant_locations.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(plant_locations)
