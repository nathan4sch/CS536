# MY README

## TODO
- Verify that our code does what it claims to do
    - Specifically, make sure we are calculating the results correctly
- Write code to generate some plots of this stuff. We need to compare throughput values in one at least.
    - Reference the plots in our Assignment 2 report

## How to run

The main script to run is `run_cc_experiment.sh`.
- The 1st argument is the cc algorithm to use. The options are ["our_cc", "cubic", "reno", "all"].
- The 2nd argument is the number of random servers to run on OR a text file containing a list of servers to run on
- The 3rd argument is the number of runs per server.
- This script sets up everything including the necessary environment stuff on my Ubuntu 24 laptop.

The scripts mostly do unreadable scripting things.

### Viewing results

Results are saved under the created `Results/` directory. Tip: use `xan v file.csv` to view csv files in terminal.

Various statistics for each run by each algorithm at time intervals are saved in csv files. When all are ran, there is also a comparison csv file created. These both need to be improved.

## How it knows what congestion control algorithm to use

When the code is ran with our_cc, we use `sudo insmod tcp_our_cc.ko` to register it into the kernal. This `.ko` file is generated from the related C `tcp_our_cc.c` file where the actual algorithm is written in C.
For cubic/reno, the `net.ipv4.tcp_allowed_congestion_control` variable is updated to specify that algorithm.

In the actual code, in `iperf3_client.py` from `Assignment_2` `_make_tcp_socket()` is used with the algorithm as an option, which is passed in from the script calling it. cubic/reno use built-in kernel stuff so we do not have to do anything except specify with the string name in the function call.

When we are done using our_cc, `sudo rmmod tcp_our_cc` is used to unload it from the kernel.

## Using the socket program from Assignment 2

The script `run_option1_tests.py` calls `iperf3_client.py` from Assignment 2 and uses it as the socket. I had to change part of the file to make this work so hopefully that didn't break anything.
