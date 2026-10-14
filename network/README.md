# Network Monitoring Agent & Controller Layer

## 1. Overview
The networking layer provides lightweight endpoint monitoring and central telemetry aggregation across the Small LAN / Mininet environment, implemented in Python with direct CLI entrypoints.

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
            NETWORK CONTROLLER
           (network_controller:5000)
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
      Console Output     CSV / JSONL Logs
                       (data/monitoring/)
```

---

## 2. Directory Structure

```
network/
├── agent/
│   ├── monitor_agent.py         # Agent CLI, sampling loop, and signal handling
│   ├── flow_monitor.py          # /proc/net/tcp & /proc/net/udp flow detection
│   ├── network_stats.py         # Interface throughput and timestamp calculations
│   ├── socket_client.py         # TCP socket streaming client, send_all, and reconnect
│   ├── main.py                  # Standby skeleton entrypoint
│   ├── monitor_agent            # Executable script
│   └── Makefile                 # Module Makefile
├── controller/
│   ├── network_controller.py    # Multi-threaded TCP server listening on port 5000
│   ├── client_handler.py        # Per-client thread worker with stream buffer & validator
│   ├── adaptive_controller.py   # Adaptive Traffic Controller (Phase 14)
│   ├── control_interface.py     # Intent dispatcher and rule lifecycle manager
│   ├── flow_mapper.py           # 5-tuple parsing, device IP & interface resolution
│   ├── tc_manager.py            # Linux traffic control (tc) HTB hierarchy manager
│   ├── control_logger.py        # State and action audit logger
│   ├── rollback.py              # Interface reset and rollback operations
│   ├── main.py                  # Standby skeleton entrypoint
│   ├── network_controller       # Executable script
│   ├── adaptive_controller      # Executable script
│   ├── Makefile                 # Module Makefile
│   └── README.md                # Controller & protocol documentation
├── ingestion/
│   ├── record_parser.py         # Pipe-delimited record parser
│   ├── data_validator.py        # Schema and network ranges integrity validator
│   ├── data_store.py            # Ring buffer, device tracking, and CSV/JSONL store
│   ├── data_ingestion.py        # Global ingestion pipeline manager
│   ├── Makefile                 # Module Makefile
│   └── README.md                # Ingestion documentation
├── topology/
│   ├── lan_topology.py          # Mininet Small LAN topology
│   └── README.md                # Topology documentation
├── traffic/
│   ├── traffic_generator.py     # iperf3 traffic generator
│   ├── traffic_scenarios.py     # 6 Predefined scenarios
│   ├── config.py                # Network and flow configuration
│   └── README.md                # Traffic generator documentation
├── common/
│   ├── protocol.py              # Common protocol binary headers & enums
│   └── __init__.py              # Common exports
├── Makefile                     # Top-level build/target manager
└── README.md                    # Networking layer documentation
```

---

## 3. Quick Start & Execution

### A. Setup Executables
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
