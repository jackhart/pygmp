# pygmp - A Python Library for Multicast Routing in Linux

Python interface and services for Linux multicast routing.


## Limitations / Roadmap
This is a work in progress.  Currently, only IPv4 multicast routing is supported.  I've also only tested with IGMPv2 on an Ubuntu 22.04.2 LTS (v6.0.0-1013-oem) host.

The only implementation is a simple, IPv4, static multicast router with a REST API.


## Pip Install

**Coming Soon**

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
