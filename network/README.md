# Network Monitoring Agent & Controller Layer (Phases 4 & 5)

## 1. Overview
The networking layer provides low-overhead, C-based endpoint monitoring and central telemetry aggregation across the Small LAN / Mininet environment.

```
             MININET LAN / HOSTS
                      │
       ┌──────────────┼──────────────┐
       │              │              │
      h1             h2             h3
(192.168.1.10) (192.168.1.11) (192.168.1.12)
       │              │              │
 [monitor_agent] [monitor_agent] [monitor_agent]
       │              │              │
       └──────────────┼──────────────┘
                      │
                 TCP SOCKETS
          (Pipe-delimited stream)
                      │
                      ▼
            C NETWORK CONTROLLER
           (network_controller:5000)
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
      Console Output     CSV Socket Logs
                       (data/socket_logs/)
```

---

## 2. Directory Structure

```
network/
├── agent/
│   ├── monitor_agent.c          # Agent CLI, sampling loop, and signal handling
│   ├── monitor_agent.h          # Agent configuration definitions
│   ├── flow_monitor.c           # /proc/net/tcp & /proc/net/udp flow detection
│   ├── flow_monitor.h           # Flow data structures
│   ├── network_stats.c          # Interface throughput and timestamp calculations
│   ├── network_stats.h          # Network statistics structures
│   ├── socket_client.c          # TCP socket streaming client, send_all, and reconnect
│   ├── socket_client.h          # TCP socket client definitions
│   └── Makefile                 # Module Makefile
├── controller/
│   ├── network_controller.c     # Multi-threaded TCP server listening on port 5000
│   ├── network_controller.h     # Controller configuration definitions
│   ├── client_handler.c         # Per-client thread worker with stream buffer & validator
│   ├── client_handler.h         # Client handler definitions
│   ├── Makefile                 # Module Makefile
│   └── README.md                # Controller & protocol documentation
├── topology/
│   ├── lan_topology.py          # Mininet Small LAN topology
│   └── README.md                # Topology documentation
├── traffic/
│   ├── traffic_generator.py     # iperf3 traffic generator
│   ├── traffic_scenarios.py     # 6 Predefined scenarios
│   ├── config.py                # Network and flow configuration
│   └── README.md                # Traffic generator documentation
├── common/
│   └── protocol.h               # Common protocol header
├── Makefile                     # Top-level build system
└── README.md                    # Networking layer documentation
```

---

## 3. Quick Start & Execution

### A. Compile Everything
```bash
make clean && make all
```

### B. Start Central Controller
```bash
./bin/network_controller --port 5000
```

### C. Start Monitoring Agents on Hosts
```bash
./bin/monitor_agent h1 --server 127.0.0.1 --port 5000 --interval 1.0 &
./bin/monitor_agent h2 --server 127.0.0.1 --port 5000 --interval 1.0 &
./bin/monitor_agent h3 --server 127.0.0.1 --port 5000 --interval 1.0 &
```

### D. Generate Traffic (Phase 3)
```bash
python3 network/traffic/traffic_generator.py --scenario mixed --duration 10
```
