# pygmp - A Python Library for Multicast Routing in Linux

A Python library that supports interacting with the Linux kernel for multicast routing.  


## Limitations / Roadmap
This is a work in progress.  Currently, only IPv4 multicast routing is supported.  I've also only tested with IGMPv2 on an Ubuntu 22.04.2 LTS (v6.0.0-1013-oem) host.

There are no daemon implementations yet.  The only implemented program is an interactive interface.

#### Roadmap

- IGMPv3, MLD, and IPv6 support
- smcrouted daemon implementation
- pimd daemon implementation
- Dockerized daemon example
- automate testing setup & virtualize testing for multiple OS
- memory lead tests with valgrind


## Quick Start

TODO - pip installing.

### Interactive Interface

Run an interactive terminal for interacting with multicast constructs in the kernel.
```bash
sudo python3 pygmp interactive
```


### Developer Quick Start

Install the [task](https://taskfile.dev/installation) utility.  This utility is used to standardize build and test processes.

```bash
sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b /usr/local/bin
```

### Host Configuration Gotchas

Most new distibutions set the IGMP version to 3.  You'll need to set it to 2 and reboot.  Also, make sure mc_forwarding is enabled.  Change the values in `/etc/sysctl.conf`.  Then, reboot.

```
net.ipv4.ip_forward = 1
net.ipv4.conf.all.force_igmp_version = 2
net.ipv4.conf.default.force_igmp_version = 2
net.ipv4.conf.all.mc_forwarding = 1
net.ipv4.conf.default.mc_forwarding = 1
```


### Relevant RFCs

RFCs often refer to, build upon, or obsolete, previous RFCs.  This can lead to a complex web of interrelated documents.  This is my collection of RFCs relevant to multicast routing.


**IGMP**
- [RFC 1112 - Host Extensions for IP Multicasting](https://datatracker.ietf.org/doc/html/rfc1112)
- [RFC 2236 - Internet Group Management Protocol, Version 2](https://datatracker.ietf.org/doc/html/rfc2236)
- [RFC 3376 - Internet Group Management Protocol, Version 3](https://datatracker.ietf.org/doc/html/rfc3376)

**MLD**
- [RFC 2710 - Multicast Listener Discovery (MLD) for IPv6](https://datatracker.ietf.org/doc/html/rfc2710)
- [RFC 3810 - Multicast Listener Discovery Version 2 (MLDv2) for IPv6](https://datatracker.ietf.org/doc/html/rfc3810)

**IGMPv3/MLDv2**
- [RFC 4604 - Using Internet Group Management Protocol Version 3 (IGMPv3) and Multicast Listener Discovery Protocol Version 2 (MLDv2) for Source-Specific Multicast](https://datatracker.ietf.org/doc/html/rfc4604)
- [RFC 5790 - Lightweight Internet Group Management Protocol Version 3 (IGMPv3) and Multicast Listener Discovery Version 2 (MLDv2) Protocols](https://datatracker.ietf.org/doc/html/rfc5790)


- [RFC 6636 - Tuning the Behavior of the Internet Group Management Protocol (IGMP) and Multicast Listener Discovery (MLD) for Routers in Mobile and Wireless Networks](https://datatracker.ietf.org/doc/html/rfc6636)
- [RFC 7761 - Protocol Independent Multicast - Sparse Mode (PIM-SM): Protocol Specification (Revised)](https://datatracker.ietf.org/doc/html/rfc7761)
- [RFC 7762 - Protocol Independent Multicast (PIM) MIB](https://datatracker.ietf.org/doc/html/rfc7762)
- [RFC 7763 - Protocol Independent Multicast - Sparse Mode (PIM-SM) Multicast Routing Security Issues and Enhancements](https://datatracker.ietf.org/doc/html/rfc7763)
- [RFC 7764 - Protocol Independent Multicast (PIM) over Virtual Private LAN Service (VPLS)](https://datatracker.ietf.org/doc/html/rfc7764)
- [RFC 7765 - Multicast Considerations over IEEE 802 Wireless Media](https://datatracker.ietf.org/doc/html/rfc7765)
- [RFC 7766 - Protocol Independent Multicast (PIM) over Ethernet (PIM-E): Protocol Specification](https://datatracker.ietf.org/doc/html/rfc7766)



RFC112 levels of Host compliance:
- Level 0: No support for IGMP nor sending/receiving multicast packets (all packets with a Class D destination address are silently discarded).
- Level 1: Support for sending multicast packets.  No support for IGMP nor receiving multicast packets.
- Level 2: Support for sending and receiving multicast packets and IGMP messages.


ICMP and IGMP are extensions to IP.  They are implemented with the code that manages the IP / network layer.

According to the IGMPv2 standard, when a host joins a multicast group, it should transmit two membership reports separated by a short interval. This is known as the "Unsolicited Membership Report" mechanism. The interval between these two reports is specified by the "Unsolicited Report Interval" (usually around 10 seconds). By sending two reports, the protocol aims to ensure that at least one report reaches the multicast router, even if there are network issues or packet loss.

Multicast routers send Host Membership Query messages (hereinafter
called Queries) to discover which host groups have members on their
attached local networks.  Queries are addressed to the all-hosts
group (address 224.0.0.1), and carry an IP time-to-live of 1.

Version 3 adds support for "source filtering",
that is, the ability for a system to report interest in receiving
packets *only* from specific source addresses, as required to support
Source-Specific Multicast [SSM], or from *all but* specific source
addresses, sent to a particular multicast address.

Version 2, specified in
[RFC-2236], added support for "low leave latency", that is, a
reduction in the time it takes for a multicast router to learn that
there are no longer any members of a particular group present on an
attached network.

Multicast Listener Discovery (MLD) is used in a similar way by IPv6
systems.  MLD version 1 [MLD] implements the functionality of IGMP
version 2; MLD version 2 [MLDv2] implements the functionality of IGMP
version 3.