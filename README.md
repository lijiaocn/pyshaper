pyshaper
========

Pyshaper is simple Python script that can create rules for Linux
shaper using tc tool from iproute2 package.  Configuration is done
using [YAML](http://en.wikipedia.org/wiki/YAML) format.

Pyshaper uses HTB qdisc for creating classes.

Sample configuration files is as follows:

    aliases:
      FastNetwork:
        - src 192.168.224.0/20
        - src 10.149.64.0/18
      Some_Name: dst 192.168.5.18
      Other_Name:
        - dst 192.168.5.4
        - dst 192.168.5.228
      VIP:
        - dst 192.168.5.100
    
    device_name: eth0.2
    shaper:
      name: Totals
      rate: 50Mbit
      children:
        - name: FastNetwork
          rate: 40Mbit 50Mbit
        - name: Internet
          rate: 7Mbit
          children:
            - name: Good_Users
              rate: 2Mbit 3Mbit
              children:
                - {name: Some_Name, rate: even 2Mbit}
                - {name: Other_Name, rate: even 2Mbit}
                - {name: VIP, rate: 1Mbit 2Mbit}
            - name: Others
              rate: 3Mbit
              children:
                - {range: dst 192.168.5.24 192.168.5.95, rate: even 256Kbit}
                - {range: dst 192.168.5.128 192.168.5.151, rate: even 256Kbit}
                - {range: dst 192.168.5.160 192.168.5.2, rate: even 256Kbit}
        - name: DEFAULT
          rate: 64Kbit

You have 40Mbits (with ceiling at 50Mbits) access to "fast
networks".  This could be networks inside your bigger LAN, or local
IX, whatever.  Traffic to users falls into Internet group, limited at
7 Mbits, and inside it are two groups.  One is for more important
users with some higher guarantess (Some_Name and Other_Name are
guaranteed 512Kbit with peaks to 2Mbit while Good_Users limit of 2Mbit
is not reached; VIP has 1Mbit and 2Mbit peak). Other is for rest of
your workstations, simple ranges, evenly distributed traffic with
peaks of up to 256Kbit.

Another example.  Simple office, you have 10 Mbits total, fast network
with two member subnets.  Traffic from those "fast networks" is
limited to 8 Mbits, evenly distributed between LAN users (about
166Kbit per user).  Each user still can download from these networks
at speed up to 2Mbit while other users are idle (ie total download is
less than 8Mbits).

All other traffic (DEFAULT, it is all other internet) gets limited to
2Mbit, evenly distributed between users with peaks up to 256Kbits.

    aliases:
      FastNetwork:
        - src 192.168.0.0/20
        - src 10.0.0.0/18
    
    device_name: eth0.2
    shaper:
      name: Totals
      rate: 10Mbit
      children:
        - name: FastNetwork
          rate: 8Mbit
          children:
            - {range: dst 192.168.3.16 192.168.3.63, rate: even 2Mbit}
        - name: DEFAULT
          rate: 2Mbit
          children:
            - {range: dst 192.168.3.16 192.168.3.63, rate: even 256Kbit}
