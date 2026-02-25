import argparse
from iperf3_client import run_iperf_tests
# Import your Part 2 modules here later

# python3 run_experiments.py -n 5 -t 15
def main():
    parser = argparse.ArgumentParser(description="Master Execution Script for Assignment")
    
    parser.add_argument('-n', type=int, default=3, help="Number of random servers to test (Part 1)")
    parser.add_argument('-t', type=int, default=15, help="Duration of each test in seconds (Part 1)")

    args = parser.parse_args()

    print("\n" + "="*50)
    print("PARTS 1,2")
    print("="*50)
    run_iperf_tests(args.n, args.t)

if __name__ == "__main__":
    main()