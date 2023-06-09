# pygmp - Multicast Routing in Linux

Python interface and services for Linux multicast routing.


## Limitations / Roadmap
This is a work in progress.  Currently, only IPv4 multicast routing is supported.  The software has only been tested on Ubuntu 20.04, and is not garenteed to work on other distros.  The only implementation thus far is a simple, IPv4, static multicast router with a REST API.


## Quick Start

Install the library with all dependencies needed to run router services.

```bash
pip install py-gmp[daemons]
```

### IPv4 Static Multicast Routing

Setup the simple daemon's config file.  The default location for the file is at `/etc/simple.ini`.

For example, say I have two network interfaces: eth0 and br0.  I'd like route all incoming multicast for groups `239.1.0.1/24` on the eth device to the bridge.  The config file would look like this.

```ini
[phyints]
names=eth0,br0

[mroute_1]
from = eth0
group = 239.1.0.1/24
to = br0
```

Next, start the daemon.

```bash
sudo python3 -m pygmp simple
```


## Source

Install the [task](https://taskfile.dev/installation) utility.  This utility is used to standardize build and test processes.

```bash
task install
```

### IPv4 Static Multicast Routing

Run an example static multicast router implementation
```bash
task run
```

In your browser, you should be able to hit `http://172.20.0.2:8000/docs` to see the OpenAPI documentation.


### Roadmap

- finalize IPv4 simple multicast daemon implementation
- CI/CD / semantic versioning / create a pip registry
- MLD/IPv6 support
- pimd daemon implementation
- Dockerized example
- expand testing to other distros



#### Host Configuration Gotchas

Most new distibutions set the IGMP version to 3.  To test with IGMPv2, you'll need to set it to 2 and reboot.  Also, make sure mc_forwarding is enabled.  Change the values in `/etc/sysctl.conf`.  Then, reboot.

```
net.ipv4.ip_forward = 1
net.ipv4.conf.all.force_igmp_version = 2
net.ipv4.conf.default.force_igmp_version = 2
net.ipv4.conf.all.mc_forwarding = 1
net.ipv4.conf.default.mc_forwarding = 1
```
