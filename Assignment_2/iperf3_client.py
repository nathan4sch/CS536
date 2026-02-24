import socket
import json
import time
import random
import string
import struct

class Iperf3Client:
    def __init__(self, server_ip, server_port=5201, duration=60):
        self.server_ip = server_ip
        self.server_port = server_port
        self.duration = duration
        
        # We will need two separate sockets
        self.control_socket = None
        self.data_socket = None
        
        self.cookie = self._generate_cookie()

    def _generate_cookie(self):
        """unique ID so the server knows which data connection belongs to which control connection"""
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
        print("[*] Exchanging parameters with server...")
        
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
        print("[+] Parameter exchange successful.")        

    def open_data_connection(self):
        """ (iii) Open the data connection. """
        print("[*] Opening data connection...")
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.connect((self.server_ip, self.server_port))
        
        # Send the exact same cookie on this new socket so the server links them together
        self.data_socket.sendall(self.cookie.encode('ascii') + b'\0')
        print("[+] Data connection established.")

    def transmit_data(self):
        """ (iv) Transmit data continuously for a configurable duration. """
        print(f"[*] Starting data transmission for {self.duration} seconds...")
        
        chunk = b'\x00' * 131072  # payload to send
        
        start_time = time.time()
        end_time = start_time + self.duration
        
        try:
            while time.time() < end_time:
                self.data_socket.sendall(chunk)
                # TODO: Part 1(c) and 2(a) - We will pause here to extract TCP_INFO and calculate Goodput!
        except BrokenPipeError:
            print("[-] Server closed the data connection prematurely.")
            
        print("[+] Transmission complete.")

    def terminate_test(self):
        """ (v) Properly terminate the test following iperf3 semantics. """
        print("[*] Terminating test...")
        
        try:
            # Tell server the test is over
            self.control_socket.sendall(b'\x04')
            
            if self.data_socket:
                self.data_socket.close()

            self.control_socket.settimeout(2.0)
            
            # 3. Wait for the server to reply with State 13 (EXCHANGE_RESULTS = \x0d)
            # This loop also clears out any leftover bytes in the pipe
            state = self.control_socket.recv(1)
            while state and state != b'\x0d': 
                state = self.control_socket.recv(1)
                
            # 4. Build the JSON stats block 
            client_stats = {
                "cpu_util_total": 1.0,
                "cpu_util_user": 0.5,
                "cpu_util_system": 0.5,
                "sender_has_retransmits": 0,
                "congestion_used": "cubic",
                "streams": [{"id": 1, "bytes": 0, "retransmits": 0, "jitter": 0, "errors": 0, "omitted_errors": 0, "packets": 0, "omitted_packets": 0, "start_time": 0, "end_time": self.duration}]
            }
            json_str = json.dumps(client_stats).encode('ascii')
            
            # 5. Pack the length and the JSON 
            payload = struct.pack('>I', len(json_str)) + json_str
            self.control_socket.sendall(payload)
            print("[+] Sent client termination stats.")
            
            # 6. Clear the pipe by reading the server's final JSON response
            self.control_socket.recv(4096)
            print("[+] Received server termination stats.")

            # 7. THE FINAL GOODBYE: Let the server hang up first!
            # We keep reading from the pipe until the server sends a TCP FIN (which makes recv return an empty byte string)
            while True:
                final_bytes = self.control_socket.recv(1024)
                if not final_bytes: # b'' means the server closed the socket
                    break
            print("[+] Server gracefully closed the connection. Safe to exit.")
            
        except socket.timeout:
            # Timeouts are fine here, it just means the server closed early
            pass 
        except Exception as e:
            print(f"[-] Minor error during termination: {e}")
        finally:
            if self.control_socket:
                self.control_socket.close()
                print("[+] Control connection closed.")

    def run(self):
        """ The master function that orchestrates the entire test securely. """
        try:
            print(f"Connecting to {self.server_ip}...")
            self.open_control_connection()
            self.open_data_connection()
            self.transmit_data()
            self.terminate_test()
            print("Test completed successfully.")
            
        except socket.timeout:
            print(f"Error: Connection to {self.server_ip} timed out. Skipping.")
        except ConnectionRefusedError:
            print(f"Error: {self.server_ip} refused the connection. It may be overloaded.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        finally:
            # Ensure sockets are always closed even if the test crashes
            if self.control_socket:
                self.control_socket.close()
            if self.data_socket:
                self.data_socket.close()

if __name__ == "__main__":
    test_server = "127.0.0.1"
    
    # We will set duration to just 5 seconds for testing so you don't have to wait a full minute
    client = Iperf3Client(server_ip=test_server, duration=5) 
    
    # Execute the master function
    client.run()