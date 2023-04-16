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


## Quick Start

TODO - pip installing.

### Interactive Interface

Run an interactive terminal for interacting with multicast constructs in the kernel.
```bash
sudo python3 pygmp interactive
```


### Developer Quick Start

Install the [task](https://taskfile.dev/installation) utility.  This utilitiy is used to standardize build and test processes.

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
