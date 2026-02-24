import argparse
from iperf3_client import run_iperf_tests
# Import your Part 2 modules here later

# python3 run_experiments.py -n 5 -t 15
def main():
    parser = argparse.ArgumentParser(description="Master Execution Script for Assignment")
    
    # Part 1 Arguments
    parser.add_argument('-n', type=int, default=3, help="Number of random servers to test (Part 1)")
    parser.add_argument('-t', type=int, default=15, help="Duration of each test in seconds (Part 1)")
    
    # Placeholder for future Part 2 arguments
    # parser.add_argument('--ros-args', type=str, help="Example args for Part 2")

    args = parser.parse_args()

    print("\n" + "="*50)
    print("EXECUTING PART 1: NETWORK GOODPUT MEASUREMENT")
    print("="*50)
    run_iperf_tests(args.n, args.t)
    
    print("\n" + "="*50)
    print("EXECUTING PART 2: TARGET ACQUISITION / CHESS")
    print("="*50)
    # Call your Part 2 functions here
    print("Part 2 logic pending implementation.")

if __name__ == "__main__":
    main()