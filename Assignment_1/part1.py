# Nathan Schneider, Kevin Jones, Peter Henwood, Austin Lovell

import os

# FORCE single-threaded operation
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import csv
import json
import urllib.request
import subprocess
import re
import sys
import math
import time
import matplotlib.pyplot as plt

INPUT_FILE = 'listed_iperf3_servers.csv'
COMPLETE_INPUT_FILE = 'part1_outputs/server_locations.csv'
DELAY_SECONDS = 1.5

'''
we need to ping an outside server.
-We send a get request to this url that just returns the ip address of the requester
'''
def get_public_ip():
    try:
        # queries a tiny service to get the IP address as text
        with urllib.request.urlopen('http://ifconfig.me/ip', timeout=5) as response:
            return response.read().decode('utf-8').strip()
    except Exception as e:
        print(f"Default to data.cs.purdue.edu")
        return '128.10.2.13'

def get_location_data():
    print("Querying ip-api.com to get Lat Lon of IPs")
    # Initialize Targets with our IP first
    my_ip = get_public_ip()
    print(f"Detected My IP: {my_ip}")
    targets = [my_ip]

    # 1. Read the Input CSV
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('IP/HOST'):
                targets.append(row['IP/HOST'])

    # 2. Process and Write Lat Lon to new csv
    os.makedirs(os.path.dirname(COMPLETE_INPUT_FILE), exist_ok=True)
    with open(COMPLETE_INPUT_FILE, 'w', newline='', encoding='utf-8') as out_f:
        fieldnames = ['IP', 'Latitude', 'Longitude', 'City', 'Country']
        writer = csv.DictWriter(out_f, fieldnames=fieldnames)
        writer.writeheader()

        total = len(targets)

        for i, ip in enumerate(targets, 1):            
            # Queries ip-api.com to get Lat/Lon.
            url = f"http://ip-api.com/json/{ip}"
            geo_data = None
            try:
                # 5 second timeout to prevent hanging
                with urllib.request.urlopen(url, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    
                    if data['status'] == 'success':
                        geo_data = {
                            'ip': ip,
                            'lat': data['lat'], 
                            'lon': data['lon'],
                            'city': data.get('city', 'Unknown'),
                            'country': data.get('country', 'Unknown')
                        }
                    else:
                        geo_data = None
            except Exception as e:
                print(f"  [!] Error fetching {ip}: {e}")
                return None

            if geo_data:
                writer.writerow({
                    'IP': ip,
                    'Latitude': geo_data['lat'],
                    'Longitude': geo_data['lon'],
                    'City': geo_data['city'],
                    'Country': geo_data['country']
                })
                out_f.flush() 
            else:
                writer.writerow({'IP': ip, 'Latitude': '', 'Longitude': '', 'City': 'Failed', 'Country': ''})

            time.sleep(DELAY_SECONDS)

    print("Lat Lon data sent to server_locations.csv")


def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates distance between two points on the Earth.
    Returns: Distance in Kilometers (km).
    """
    R = 6371.0  # Radius of Earth in kilometers

    # Convert degrees to radians
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    distance = R * c
    return distance

def get_ping_stats(target, count=100, interval=0.01):
    """
    Pings a target
    Returns: dict {'min': float, 'avg': float, 'max': float} or None if failed.
    """
    # -c: Count (number of pings)
    # -i: Interval (wait time between pings in seconds)
    command = ['ping', '-c', str(count), '-i', str(interval), target]
    
    try:
        # Run the command and capture output
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            return None

        pattern = r"rtt min/avg/max/mdev = ([0-9.]+)/([0-9.]+)/([0-9.]+)/[0-9.]+ ms"
        match = re.search(pattern, result.stdout)
        
        if match:
            return {
                'min': float(match.group(1)),
                'avg': float(match.group(2)),
                'max': float(match.group(3))
            }
        else:
            return None

    except Exception as e:
        print(f"Error executing ping subprocess: {e}")
        return None

def create_scatter_plot(results):
    """
    Generates a PDF scatter plot of Distance vs RTT.
    """
    
    distances = []
    rtts = []
    
    for item in results:
        # Filter out "Unknown" distances or 0 distance (local) if desired
        if item['dist'] is not None and item['dist'] >= 0:
            distances.append(item['dist'])
            rtts.append(item['stats']['avg']) # Using Average RTT

    if not distances:
        print("No valid data points to plot.")
        return

    plt.figure(figsize=(10, 6))
    plt.scatter(distances, rtts, color='blue', alpha=0.7, edgecolors='black')
    
    plt.title("Distance vs Round Trip Time (RTT)")
    plt.xlabel("Geographical Distance (km)")
    plt.ylabel("Average RTT (ms)")
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # Save directly to PDF
    os.makedirs('part1_outputs', exist_ok=True)
    output_filename = "part1_outputs/rtt_vs_distance.pdf"
    plt.savefig(output_filename)
    print(f"Plot saved successfully as '{output_filename}'")
    
    plt.close()


def main():
    # Hardcoded Location: West Lafayette, IN (Purdue)
    get_location_data()

    origin_lat = 40.4444
    origin_lon = -86.9256
    
    results = []

    print("-" * 110)
    print(f"{'Target':<30} {'Status':<8} {'Min RTT (ms)':<10} {'Max RTT (ms)':<10} {'Avg RTT (ms)':<10} {'Distance (km)':<15}")
    print("-" * 110)

    try:
        with open(COMPLETE_INPUT_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                target = row['IP']
                target_lat = float(row['Latitude'])
                target_lon = float(row['Longitude'])

                # STEP 1: Ping
                stats = get_ping_stats(target)

                if stats:
                    # STEP 2: Calculate Distance directly from CSV data
                    dist_km = calculate_haversine_distance(
                        origin_lat, origin_lon,
                        target_lat, target_lon
                    )
                    dist_display = f"{dist_km:.1f}"

                    # Print stats
                    print(f"{target:<30} {'UP':<8} {stats['min']:<10.2f} {stats['max']:<10.2f} {stats['avg']:<10.2f} {dist_display:<15}")

                    results.append({
                        'ip': target,
                        'stats': stats,
                        'dist': dist_km
                    })
                else:
                    print(f"{target:<30} {'DOWN':<8} {'-':<10} {'-':<10} {'-':<10} {'-':<15}")

    except FileNotFoundError:
        print(f"Error: Could not find {COMPLETE_INPUT_FILE}.")
    except Exception as e:
        print(f"Error: {e}")

    print("-" * 110)
    print(f"Experiment Finished. Successful pings: {len(results)}")

    # STEP 3: Generate Plot
    if results:
        create_scatter_plot(results)



if __name__ == "__main__":
    main()