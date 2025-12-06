import csv
import os
import requests
import concurrent.futures
from dotenv import load_dotenv
load_dotenv()
import pandas as pd
api_key = os.getenv("GOOGLE_API_KEY")
log_file = "progress_log.csv"
final_matrix_file = "final_distance_matrix_60k.csv"

# read possible facility locations
possible_facilities = []
with open("possible_facilities.csv", "r") as f:
    reader = csv.reader(f)
    for row in reader:
        latitude = float(row[0])
        longitude = float(row[1])
        possible_facilities.append((latitude, longitude))
# read cleaned plant locations
plant_locations = []
with open("cleaned_plant_locations.csv", "r") as f:
    reader = csv.reader(f)
    for row in reader:
        latitude = float(row[1])
        longitude = float(row[2])
        plant_locations.append((latitude, longitude))

facility = possible_facilities[0]
plant = plant_locations[0]

def get_distance(pair, API_KEY=api_key, URL="https://maps.googleapis.com/maps/api/distancematrix/json"):
    """
    Worker function for threading.
    pair: tuple ((lat1, lon1), (lat2, lon2))
    """
    indices, origin, dest = pair
    idx1, idx2 = indices
    origin_str = f"{origin[0]},{origin[1]}"
    dest_str = f"{dest[0]},{dest[1]}"
    
    params = {
        "origins": origin_str,
        "destinations": dest_str,
        "mode": "driving",
        "key": API_KEY
    }
    
    try:
        # Added timeout so script doesn't hang forever on bad network
        response = requests.get(URL, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") == "OK":
            element = data["rows"][0]["elements"][0]
            if element.get("status") == "OK":
                dist = element["distance"]["value"] # Meters
                return (idx1, idx2, dist)
            else:
                # Handle cases like points in ocean/forest
                return (idx1, idx2, "ZERO_RESULTS")
        else:
            return (idx1, idx2, f"API_ERR_{data.get('status')}")
    except Exception as e:
        # Network error or parsing error
        return (idx1, idx2, "NET_ERR")

# Track completed requests
completed_keys = set()
results_store = {}

# If log exists, load what we already paid for
if os.path.exists(log_file):
    print(f"Found existing log file '{log_file}'. Resuming...")
    with open(log_file, "r") as f:
        reader = csv.reader(f)
        next(reader, None) # Skip header
        for row in reader:
            if row:
                r_idx, c_idx, val = int(row[0]), int(row[1]), row[2]
                completed_keys.add((r_idx, c_idx))
                results_store[(r_idx, c_idx)] = val
    print(f"Already completed: {len(completed_keys)} requests.")

# Generate tasks
pairs = []
rows, cols = len(possible_facilities), len(plant_locations)
for idx1, facility in enumerate(possible_facilities[:rows]):
    for idx2, plant in enumerate(plant_locations[:cols]):
        indices = [idx1, idx2]
        if (idx1, idx2) not in completed_keys:
            pairs.append((indices, facility, plant))
        
print(pairs)
print(f"Processing {len(pairs)} requests...")
results = []
matrix = [[None for _ in range(cols)] for _ in range(rows)]

if pairs:
    if not os.path.exists(log_file):
        with open(log_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Row_Index", "Col_Index", "Distance_Value"])

    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Submit as generator
            future_to_task = {executor.submit(get_distance, t): t for t in pairs}
            
            completed_in_session = 0
            for future in concurrent.futures.as_completed(future_to_task):
                i, j, dist = future.result()
                
                # Handle the result
                if dist is None: dist = "ERROR"
                
                # 1. Write to disk immediately (Safety)
                writer.writerow([i, j, dist])
                
                # 2. Store in memory for final matrix
                results_store[(i, j)] = dist
                
                # 3. Progress Bar
                completed_in_session += 1
                if completed_in_session % 100 == 0:
                    print(f"Session Progress: {completed_in_session}/{len(pairs)}")
                    f.flush() # Force write to disk

# save distance matrix to csv
for i in range(rows):
    for j in range(cols):
        matrix[i][j] = results_store[(i, j)]
        if matrix[i][j] == "ZERO_RESULTS":
            print((i, j))

with open("distance_matrix.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(matrix)
