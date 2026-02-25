import socket
import json
import time
import random
import string
import struct
import argparse
import matplotlib.pyplot as plt
import numpy as np
import csv
import graph_generator

TCP_INFO = 11

class Iperf3Client:
    def __init__(self, server_ip, server_port=5201, duration=60):
        self.server_ip = server_ip
        self.server_port = server_port
        self.duration = duration
        
        self.control_socket = None
        self.data_socket = None
        self.cookie = self._generate_cookie()

        self.tcp_stats = []

    def _generate_cookie(self):
        chars = string.ascii_letters + string.digits
        cookie = ''.join(random.choice(chars) for _ in range(36))
        return cookie

    def open_control_connection(self):
        """ (i) Establish the control connection. """
        print(f"[*] Attempting to connect to {self.server_ip} on port {self.server_port}...")
        
        # Create a standard IPv4 (AF_INET) TCP (SOCK_STREAM) socket
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_socket.settimeout(5.0) 
        self.control_socket.connect((self.server_ip, self.server_port))
        
        print(f"[+] Successfully connected to {self.server_ip}")

        """ (ii) Perform the JSON-based parameter exchange. """        
        # Send cookie
        self.control_socket.sendall(self.cookie.encode('ascii') + b'\0')
        self.control_socket.recv(1)
        
        # Create the JSON payload : looked at pcap file
        params = {
            "tcp": True,
            "omit": 0,
            "time": self.duration,
            "num": 0,
            "blockcount": 0,
            "parallel": 1,
            "len": 131072, 
            "pacing_timer": 1000,
            "client_version": "3.16"
        }
        json_str = json.dumps(params).encode('ascii')
        
        # Send the length of the JSON string as a 4-byte integer, followed by the JSON itself.
        self.control_socket.sendall(struct.pack('>I', len(json_str)) + json_str)
        self.control_socket.recv(1)

    def open_data_connection(self):
        """ (iii) Open the data connection. """
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.connect((self.server_ip, self.server_port))
        
        self.data_socket.sendall(self.cookie.encode('ascii') + b'\0') # send cookie

    def transmit_data(self):
        """ (iv) Transmit data continuously for a configurable duration. """
        chunk = b'\x00' * 131072  # payload to send
        
        start_time = time.time()
        end_time = start_time + self.duration

        last_check_time = start_time
        last_bytes_acked = 0
        
        try:
            while time.time() < end_time:
                self.data_socket.sendall(chunk)
                
                current_time = time.time()
                interval = current_time - last_check_time
                elapsed_test_time = current_time - start_time
                
                if interval >= 0.2:
                    try:
                        # talk to linux kernel, requests the tcp_info state machine, 128 buffer to catch answer
                        tcp_info_data = self.data_socket.getsockopt(socket.IPPROTO_TCP, TCP_INFO, 128)

                        # Part 1(a)
                        bytes_acked = struct.unpack("Q", tcp_info_data[120:128])[0] # number of bytes server has confirmed receiving
                        interval_acked = bytes_acked - last_bytes_acked
                        goodput_bps = (interval_acked / interval) * 8
                        
                        # PART 2(a)
                        # RTT (microseconds -> milliseconds)
                        rtt_us = struct.unpack("I", tcp_info_data[68:72])[0] # round trip time
                        rtt_ms = rtt_us / 1000.0
                        
                        # Congestion Window (Packets)
                        # maximum number of packets the kernel is allowed to have "in flight"
                        snd_cwnd = struct.unpack("I", tcp_info_data[80:84])[0]
                        
                        # Total Retransmissions
                        total_retrans = struct.unpack("I", tcp_info_data[100:104])[0]
                        
                        # Save everything as a structured dictionary
                        sample = {
                            "time": elapsed_test_time,
                            "goodput_bps": goodput_bps,
                            "snd_cwnd": snd_cwnd,
                            "rtt_ms": rtt_ms,
                            "total_retrans": total_retrans
                        }
                        self.tcp_stats.append(sample)
                        
                        last_bytes_acked = bytes_acked
                        last_check_time = current_time
                        
                    except Exception as e:
                        if isinstance(e, ConnectionAbortedError):
                            raise e
                        pass
                        
        except (BrokenPipeError, ConnectionResetError):
            print("[-] Server closed the data connection prematurely.")


    # this part might still be wrong
    # iperf3 -s, python3 iperf3_client.py
    def terminate_test(self):
        """ (v) Properly terminate the test following iperf3 semantics. """
        
        try:
            # Tell the server the test is over
            self.control_socket.sendall(b'\x04')
            
            if self.data_socket:
                self.data_socket.close()

            self.control_socket.settimeout(2.0)
            
            state = self.control_socket.recv(1)
            while state and state != b'\x0d': 
                state = self.control_socket.recv(1)
                
            client_stats = {
                "cpu_util_total": 1.0,
                "cpu_util_user": 0.5,
                "cpu_util_system": 0.5,
                "sender_has_retransmits": 0,
                "congestion_used": "cubic",
                "streams": [{"id": 1, "bytes": 0, "retransmits": 0, "jitter": 0, "errors": 0, "omitted_errors": 0, "packets": 0, "omitted_packets": 0, "start_time": 0, "end_time": self.duration}]
            }
            json_str = json.dumps(client_stats).encode('ascii')
            payload = struct.pack('>I', len(json_str)) + json_str
            self.control_socket.sendall(payload)
            
            self.control_socket.recv(4096)
            
            state = self.control_socket.recv(1)
            while state and state != b'\x0e':
                state = self.control_socket.recv(1)
            
            self.control_socket.sendall(b'\x0f')
            
        except socket.timeout:
            pass 
        except Exception as e:
            print(f"[-] error during termination: {e}")
        finally:
            if self.control_socket:
                self.control_socket.close()
                print("[+] Control connection closed.")

    def run(self):
        try:
            self.open_control_connection()
            self.open_data_connection()
            self.transmit_data()
            self.terminate_test()
            return True, self.tcp_stats
            
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            if self.control_socket: self.control_socket.close()
            if self.data_socket: self.data_socket.close()
            return False, []

# python3 run_experiments.py -n 5 -t 15
# docker run --rm --network host -v $(pwd):/app cs536-assign2 -n 1 -t 30
def run_iperf_tests(num_servers, duration):
    public_servers = []
    
    # extract servers from csv
    try:
        with open('iperf3serverlist.csv', mode='r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                host = row['IP/HOST']
                port_str = row['PORT']
                
                if not host or not port_str:
                    continue 
                
                if '-' in port_str:
                    port = int(port_str.split('-')[0])
                else:
                    port = int(port_str)
                    
                public_servers.append((host, port))
    except FileNotFoundError:
        print("[-] Error: 'iperf3serverlist.csv' not found in the current directory.")
        exit()
    
    random.shuffle(public_servers)
    
    successful_tests = 0
    server_index = 0
    all_results = {}

    # do 'n' tests
    while successful_tests < num_servers and server_index < len(public_servers):
        target_ip, target_port = public_servers[server_index]
        print(f"--- Test {successful_tests + 1}/{num_servers}: {target_ip}:{target_port} ---")
        
        client = Iperf3Client(server_ip=target_ip, server_port=target_port, duration=duration)
        success, tcp_stats = client.run()
        
        if success and len(tcp_stats) > 0:
            all_results[target_ip] = tcp_stats
            successful_tests += 1
            print(f"[+] Successfully captured Goodput data for {target_ip}\n")
        else:
            print(f"[-] Test failed or rate-limited. Skipping to replacement server...\n")
            
        server_index += 1

    # save data to json
    json_filename = "tcp_metrics.json"
    with open(json_filename, "w") as f:
        json.dump(all_results, f, indent=4)
    print(f"\n[+] Saved all TCP metrics to '{json_filename}'")

    graph_generator.main()

# Allows the script to still be run independently if needed
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="iPerf3 Client with Goodput Measurement")
    parser.add_argument('-n', type=int, default=3, help="Number of random servers to test")
    parser.add_argument('-t', type=int, default=15, help="Duration of each test in seconds")
    args = parser.parse_args()
    run_iperf_tests(args.n, args.t)