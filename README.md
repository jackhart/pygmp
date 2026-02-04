# pygmp - Multicast Routing in Linux

Python interface and services for Linux IPv4 multicast routing. Provides a simple static multicast router with a REST API and a Python/C extension for direct kernel multicast routing table (MRT) control.

## Features

- **Static multicast routing daemon** with REST API (FastAPI/Uvicorn)
- **Wildcard routes** with CIDR prefix matching (e.g., `239.1.0.0/24`)
- **Dynamic route handling** — the kernel notifies the daemon of unmatched multicast traffic, and the daemon installs forwarding rules on demand
- **Source-Specific Multicast (SSM)** — route based on both source IP and multicast group
- **C extension** for low-level kernel MRT interaction via raw sockets
- **Interactive shell** for manual multicast routing configuration and debugging

## Limitations

This is a work in progress. Currently, only IPv4 multicast routing is supported. The software has only been tested on Ubuntu 20.04 and may not work on other distributions. IPv6 / MLD support is planned.

## Quick Start

Install the library with daemon dependencies:

```bash
pip install py-gmp[daemons]
```

### Configuration

Create a configuration file (default: `/etc/simple.ini`). The file uses INI format with two types of sections:

#### Physical Interfaces

The `[phyints]` section lists the network interfaces to use for multicast routing:

```ini
[phyints]
names=eth0,br0
```

All listed interfaces must exist, have at least one IP address, and be multicast-capable.

#### Multicast Routes

Each route is defined in a `[mroute_N]` section (where N is any unique identifier):

```ini
[mroute_1]
from = eth0
group = 239.1.0.0/24
to = br0
```

**Route fields:**

| Field    | Required | Description |
|----------|----------|-------------|
| `from`   | Yes      | Incoming interface name |
| `group`  | Yes      | Multicast group address or CIDR network (e.g., `239.0.0.1` or `239.1.0.0/24`) |
| `to`     | Yes      | Outgoing interfaces with optional TTL thresholds (e.g., `br0=2,eth1=1` or just `br0`) |
| `source` | No       | Source IP for SSM. Defaults to `0.0.0.0` (any source / wildcard) |

#### Route Types

**Static routes** have an explicit `source` IP address. These are installed directly into the kernel's Multicast Forwarding Cache (MFC) at startup and forward traffic from that specific source.

**Dynamic/wildcard routes** have `source = 0.0.0.0` (or omit the `source` field). These are stored in memory as matching rules. When the kernel receives a multicast packet with no MFC entry, it sends an `IGMPMSG_NOCACHE` control message to the daemon. The daemon then checks its dynamic rules, and if one matches the packet's group (including CIDR prefix matches), it installs a temporary MFC entry.

#### Example Configurations

**Simple forwarding** — route all multicast for group `239.0.0.4` arriving on `eth0` to `br0`:

```ini
[phyints]
names=eth0,br0

[mroute_1]
from = eth0
group = 239.0.0.4
to = br0
```

**Wildcard group with CIDR** — route all `239.1.x.x` multicast to two interfaces:

```ini
[phyints]
names=eth0,br0,eth1

[mroute_1]
from = eth0
group = 239.1.0.0/16
to = br0=2,eth1=1
```

**Source-Specific Multicast** — only forward traffic from `192.168.2.1`:

```ini
[phyints]
names=eth0,br0,eth1

[mroute_1]
from = eth0
source = 192.168.2.1
group = 224.0.1.0
to = br0,eth1=2
```

**Mixed static and dynamic routes:**

```ini
[phyints]
names=a1,a2,a3

[mroute_1]
from = a1
group = 239.0.0.4
to = a2=2

[mroute_2]
from = a1
source = 192.168.2.1
group = 224.0.1.0
to = a2,a3=2
```

### Running the Daemon

The daemon requires root privileges (raw socket access).

```bash
# Run in the foreground (Ctrl+C to stop)
sudo python3 -m pygmp simple --config /etc/simple.ini

# Run as a background daemon
sudo python3 -m pygmp --daemon simple --config /etc/simple.ini

# Specify REST API host and port
sudo python3 -m pygmp --host 0.0.0.0 --port 9000 simple --config /etc/simple.ini
```

**CLI options:**

| Option      | Default          | Description |
|-------------|------------------|-------------|
| `--host`    | `0.0.0.0`        | REST API listen address |
| `--port`    | `8000`           | REST API listen port |
| `--daemon`  | off              | Run as background daemon (double-fork) |
| `--config`  | `/etc/simple.ini`| Path to configuration file |

## REST API

Once the daemon is running, the REST API is available. OpenAPI documentation is auto-generated at `http://<host>:<port>/docs`.

### Endpoints

#### Virtual Interfaces (VIFs)

| Method   | Path                      | Description |
|----------|---------------------------|-------------|
| `GET`    | `/vifs`                   | List all registered virtual interfaces |
| `GET`    | `/vifs/{interface_name}`  | Get a specific VIF by interface name |
| `POST`   | `/vifs`                   | Add a new VIF (params: `interface_address_or_index`, optional `mcast_index`) |
| `DELETE` | `/vifs/{interface_name}`  | Remove a VIF by interface name |

#### Multicast Forwarding Cache (MFC)

| Method   | Path                        | Description |
|----------|-----------------------------|-------------|
| `GET`    | `/static_mfc`              | List all static MFC entries (from kernel) |
| `GET`    | `/static_mfc/{vif_index}`  | List static MFC entries for a specific incoming VIF |
| `GET`    | `/dynamic_mfc`             | List all dynamic/wildcard route rules (in-memory) |
| `GET`    | `/dynamic_mfc/{vif_index}` | List dynamic route rules for a specific incoming VIF |
| `POST`   | `/mfc`                     | Add a multicast route (body: MRoute JSON) |
| `DELETE` | `/mfc`                     | Remove a multicast route (body: MRoute JSON) |

#### MRoute JSON Format

```json
{
  "from_": "eth0",
  "group": "239.0.0.4",
  "to": {"br0": 2, "eth1": 1},
  "source": "0.0.0.0"
}
```

### Example API Usage

```bash
# List all VIFs
curl http://localhost:8000/vifs

# Get a specific VIF
curl http://localhost:8000/vifs/eth0

# List static MFC entries
curl http://localhost:8000/static_mfc

# List dynamic route rules
curl http://localhost:8000/dynamic_mfc

# Add a dynamic route via the API
curl -X POST http://localhost:8000/mfc \
  -H "Content-Type: application/json" \
  -d '{"from_": "eth0", "group": "239.0.0.5", "to": {"br0": 1}}'

# Remove a route
curl -X DELETE http://localhost:8000/mfc \
  -H "Content-Type: application/json" \
  -d '{"from_": "eth0", "group": "239.0.0.5", "to": {"br0": 1}}'
```

## Architecture

```
┌──────────────────────────────────────────────────┐
│                   REST API (FastAPI)              │
│  GET/POST/DELETE  /vifs  /static_mfc  /dynamic_mfc  /mfc │
├──────────────────────────────────────────────────┤
│              Simple Daemon (simple.py)            │
│   VifManager  │  MfcManager  │  ControlMsgHandler │
├──────────────────────────────────────────────────┤
│              Kernel API (kernel.py)               │
│   igmp_socket  add_vif  add_mfc  flush  parse_*  │
├──────────────────────────────────────────────────┤
│            C Extension (_kernel.c)                │
│   setsockopt  ioctl  parse_ip_header  parse_igmp  │
├──────────────────────────────────────────────────┤
│           Linux Kernel MRT (ipmr.c)               │
│   /proc/net/ip_mr_vif   /proc/net/ip_mr_cache    │
└──────────────────────────────────────────────────┘
```

**VifManager** — manages virtual interface registrations in the kernel. Maps physical interfaces to VIF indices used by the MFC.

**MfcManager** — manages multicast forwarding rules. Static routes (with explicit source) are installed directly into the kernel MFC. Dynamic routes (any-source) are stored in memory and applied on demand when the kernel reports unmatched packets.

**ControlMessageHandler** — listens on the IGMP socket for kernel control messages (`IGMPMSG_NOCACHE`). When unmatched multicast arrives, it looks up a matching dynamic rule and installs an MFC entry.

## Developer Quick Start

Install [task](https://taskfile.dev/installation) for build automation:

```bash
task install
```

### Running Tests

Tests require root privileges and create network namespaces with dummy interfaces.

```bash
task test
```

### Running a Development Instance

Start the daemon in a test network namespace:

```bash
task run
```

Then access the OpenAPI docs at `http://172.20.0.2:8000/docs`.

### Project Structure

```
pygmp/
├── __init__.py          # Package init
├── __main__.py          # CLI entry point
├── kernel.py            # High-level kernel MRT API
├── data.py              # Data structures (dataclasses, enums)
├── utils.py             # Utilities (file cache, IP conversion)
├── _kernel.c / .h       # C extension for kernel syscalls
├── _kernel.pyi          # Type stubs for the C extension
├── util.c / .h          # C utility functions
├── log_config.ini       # Logging configuration
├── Makefile             # C compilation
└── daemons/
    ├── __init__.py
    ├── simple.py        # Simple static multicast daemon + REST API
    ├── interactive.py   # Interactive shell for manual routing
    ├── config.py        # INI configuration parser
    └── utils.py         # Daemon utilities (fork, PID, signals, logging)
```

## Roadmap

- Finalize IPv4 simple multicast daemon implementation
- Improve CI/CD, versioning, and test coverage
- MLD / IPv6 support
- Containerized deployment example
- PIM daemon implementation

## Host Configuration

Most modern Linux distributions default to IGMPv3. For testing with IGMPv2, update `/etc/sysctl.conf` and reboot:

```
net.ipv4.ip_forward = 1
net.ipv4.conf.all.force_igmp_version = 2
net.ipv4.conf.default.force_igmp_version = 2
net.ipv4.conf.all.mc_forwarding = 1
net.ipv4.conf.default.mc_forwarding = 1
```

## License

MIT License. See [LICENSE](LICENSE) for details.
