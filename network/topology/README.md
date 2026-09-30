# Phase 2: Small LAN Testbed & Topology

## Overview
This module defines the **Small LAN Network Topology** simulated via **Mininet**. It supports 2 to 50 client hosts connected via a central gateway switch (`s1`), with configurable link bandwidth, latency, and packet loss.

```
            +--------------------+
            |   Gateway Switch   | (s1 / 192.168.1.1)
            +---------+----------+
                      |
         +------------+------------+ ... +
         |            |            |     |
      +--+---+     +--+---+     +--+---+ +--+---+
      |  h1  |     |  h2  |     |  h3  | |  hN  |
      +------+     +------+     +------+ +------+
   (192.168.1.10) (192.168.1.11) (192.168.1.12)
```

---

## 🚀 How to Run the Topology

### 1. Start with Default Parameters (5 Hosts, 100Mbps, 2ms delay)
```bash
sudo python3 network/topology/lan_topology.py
```

### 2. Custom Scaling (e.g. 15 Hosts, 50Mbps, 5ms delay, 1% loss)
```bash
sudo python3 network/topology/lan_topology.py --hosts 15 --bw 50 --delay 5ms --loss 1.0
```

### 3. Run Automated Connectivity Test & Exit
```bash
sudo python3 network/topology/lan_topology.py --test --no-cli
```

### 4. Interactive Mininet CLI Commands
Inside the Mininet CLI:
```bash
# Test connectivity between all hosts
mininet> pingall

# Test host-to-host ping
mininet> h1 ping -c 3 h2

# Start an iperf3 server on h2
mininet> h2 iperf3 -s &

# Run TCP bandwidth test from h1 to h2
mininet> h1 iperf3 -c 192.168.1.11 -t 10

# Run UDP bandwidth test from h1 to h2 (10 Mbps)
mininet> h1 iperf3 -c 192.168.1.11 -u -b 10M -t 10

# Exit topology
mininet> exit
```
