# Nathan Schneider, Kevin Jones, Peter Henwood, Austin Lovell

'''
-Windows diagnostic test. Sends tiny packet to the destination to see if its there.
-n tells that we want to define the number of echo requests to send
-In this example, system sends 5 packets.

Ping statistics for 160.242.19.254:
    Packets: Sent = 5, Received = 5, Lost = 0 (0% loss),
Approximate round trip times in milli-seconds:
    Minimum = 225ms, Maximum = 225ms, Average = 225ms
'''
# ping -c 5 google.com
# ping -c 100 -i 0.2 google.com

# hardcode my current location / ip
# exclude the non-responsive servers, use a timeout in the script to skip if it doesnt respond in a certain amount of times
# do at least 100 pings for each server. Use the -i flag to ping faster

# need to make a report as well? What all is in there
# can I just assume that they will test it on windows?

#The -i thing he mentioned is a thing for linux? Should I not be using windows and run this on the purdue machines.\

# todo, retry the down process
# get accurate locations? Redo the api calls?
# figure out the plot?

import os

# FORCE single-threaded operation to avoid crashing university servers
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import csv
import subprocess
import re
import sys
import json
import urllib.request
import math
import time
import matplotlib.pyplot as plt


# should I redo this or hardcode?
def get_location_data(ip_address):
    """
    Queries ip-api.com to get Lat/Lon for a specific IP.
    Returns: dict {'lat': float, 'lon': float} or None.
    """
    url = f"http://ip-api.com/json/{ip_address}"
    try:
        # 5 second timeout to prevent hanging
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data['status'] == 'success':
                return {'lat': data['lat'], 'lon': data['lon']}
            return None
    except Exception as e:
        # print(f"Geo lookup failed: {e}") # Uncomment to debug
        return None
    

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points on the Earth.
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

# add something to retry the pinging to make sure the host is dead
def get_ping_stats(target, count=1, interval=0.01):
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
        
        # If the ping command failed (exit code != 0), it might be a dead host
        if result.returncode != 0:
            return None

        # Linux Output: "rtt min/avg/max/mdev = 49.123/50.456/52.789/1.234 ms"
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

    print("Generating scatter plot...")
    
    distances = []
    rtts = []
    
    # Extract valid data points
    for item in results:
        # Filter out "Unknown" distances or 0 distance (local) if desired
        if item['dist'] is not None and item['dist'] >= 0:
            distances.append(item['dist'])
            rtts.append(item['stats']['avg']) # Using Average RTT

    if not distances:
        print("No valid data points to plot.")
        return

    # Create the Plot
    plt.figure(figsize=(10, 6))
    plt.scatter(distances, rtts, color='blue', alpha=0.7, edgecolors='black')
    
    # Formatting
    plt.title("Distance vs Round Trip Time (RTT)")
    plt.xlabel("Geographical Distance (km)")
    plt.ylabel("Average RTT (ms)")
    plt.grid(True, linestyle='--', alpha=0.6)
    
    # Save directly to PDF
    output_filename = "rtt_vs_distance.pdf"
    plt.savefig(output_filename)
    print(f"Plot saved successfully as '{output_filename}'")
    
    # Close plot to free memory
    plt.close()


def main():
    # Hardcoded Location: West Lafayette, IN (Purdue)
    origin_lat = 40.4237
    origin_lon = -86.9212
    
    input_file = 'listed_iperf3_servers.csv'
    
    results = []

    print("-" * 110)
    print(f"{'Target':<30} {'Status':<8} {'Min RTT':<10} {'Max RTT':<10} {'Avg RTT':<10} {'Distance (km)':<15}")
    print("-" * 110)

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                target = row['IP/HOST']
                if not target: continue

                # STEP 1: Ping
                stats = get_ping_stats(target)

                if stats:
                    # STEP 2: Geolocation & Distance
                    geo_data = get_location_data(target)
                    
                    dist_km = 0.0
                    if geo_data:
                        dist_km = calculate_haversine_distance(
                            origin_lat, origin_lon,
                            geo_data['lat'], geo_data['lon']
                        )
                        dist_display = f"{dist_km:.1f}"
                    else:
                        dist_display = "Unknown"

                    # Print all stats clearly
                    print(f"{target:<30} {'UP':<8} {stats['min']:<10.2f} {stats['max']:<10.2f} {stats['avg']:<10.2f} {dist_display:<15}")

                    results.append({
                        'ip': target,
                        'stats': stats,
                        'dist': dist_km
                    })
                    
                    time.sleep(0.5) 
                else:
                    print(f"{target:<30} {'DOWN':<8} {'-':<10} {'-':<10} {'-':<10} {'-':<15}")

    except FileNotFoundError:
        print(f"Error: Could not find {input_file}.")
    except Exception as e:
        print(f"Error: {e}")

    print("-" * 110)
    print(f"Experiment Finished. Successful pings: {len(results)}")

    # STEP 3: Generate Plot
    if results:
        create_scatter_plot(results)



if __name__ == "__main__":
    main()