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
# ping -n 5 160.242.19.254

# hardcode my current location / ip
# exclude the non-responsive servers, use a timeout in the script to skip if it doesnt respond in a certain amount of times
# do at least 100 pings for each server. Use the -i flag to ping faster

# need to make a report as well? What all is in there
# can I just assume that they will test it on windows?

#The -i thing he mentioned is a thing for linux? Should I not be using windows and run this on the purdue machines.