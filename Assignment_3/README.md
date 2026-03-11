# README

## How to run

The main script to run is `run_cc_experiment.sh`.
- The 1st argument is the cc algorithm to use. The options are ["our_cc", "cubic", "reno", "all"].
- The 2nd argument is the number of random servers to run on OR a text file containing a list of servers to run on
- The 3rd argument is the number of runs per server.
- This script sets up everything including the necessary environment stuff on my Ubuntu 24 laptop.

The .sh script is mostly focused on validating input parameters and setting up the list of servers to run on. The .py script actually calls the socket API and also generates and saves statistics from the runs.

### Viewing results

Results are saved in .csv under the created `Results/` directory.

Various statistics for each run by each algorithm at time intervals are saved in csv files. When all are ran, there is also a comparison csv file created.

To visualize the differences between algorithms, change the file path on line 7 of Assignment_3/Generate_Plots/GeneratePlots.py and run the file. The graphs will be saved to Assignment_3/Generate_Plots/Plots.

## How it knows what congestion control algorithm to use

When the code is ran with our_cc, we use `sudo insmod tcp_our_cc.ko` to register it into the kernal. This `.ko` file is generated from the related C `tcp_our_cc.c` file where the actual algorithm is written in C.
For cubic/reno, the `net.ipv4.tcp_allowed_congestion_control` variable is updated to allow the algorithm to be used.

In the actual code, in `iperf3_client.py` from `Assignment_2` `sock.setsockopt()` is used with the algorithm as an option, which is passed in from the script calling it.

When we are done using our_cc, `sudo rmmod tcp_our_cc` is used to unload it from the kernel.

## Using the socket program from Assignment 2

The script `run_option1_tests.py` calls `iperf3_client.py` from Assignment 2 and uses it as the socket application.
