# Phase 3: Traffic Generation Module

## 🌐 Overview
The **Traffic Generation Module** generates realistic, configurable TCP and UDP synthetic traffic flows inside the **Mininet Small LAN Topology**. It serves as the baseline traffic generator before attaching low-level C network monitoring agents in later phases.

---

## 🚦 Predefined Traffic Scenarios

| Scenario Name | CLI Argument | Protocol | Flows | Description |
| :--- | :--- | :--- | :---: | :--- |
| **Normal TCP** | `--scenario tcp` | TCP | 1 | Single steady TCP stream (`h1 -> h2`) |
| **Normal UDP** | `--scenario udp` | UDP | 1 | Single constant-bitrate UDP stream (`h3 -> h4`) |
| **Multiple TCP** | `--scenario multi_tcp` | TCP | 3 | Simultaneous parallel TCP streams across hosts |
| **Multiple UDP** | `--scenario multi_udp` | UDP | 3 | Simultaneous parallel UDP streams across hosts |
| **Mixed Traffic**| `--scenario mixed` | TCP + UDP | 4 | Coexisting TCP bulk transfers and UDP streaming |
| **Congestion**   | `--scenario congestion` | TCP + UDP | 4 | Multi-stream bursts & UDP flooding inducing link saturation |

---

## 🛠 Usage & Command Line Options

### 1. Run Scenarios with Default Parameters
```bash
# Scenario 1: Normal TCP
python3 network/traffic/traffic_generator.py --scenario tcp

# Scenario 2: Normal UDP
python3 network/traffic/traffic_generator.py --scenario udp --bandwidth 15M

# Scenario 3: Multiple TCP
python3 network/traffic/traffic_generator.py --scenario multi_tcp

# Scenario 4: Multiple UDP
python3 network/traffic/traffic_generator.py --scenario multi_udp --bandwidth 8M

# Scenario 5: Mixed Traffic
python3 network/traffic/traffic_generator.py --scenario mixed

# Scenario 6: Congestion Traffic
python3 network/traffic/traffic_generator.py --scenario congestion --bandwidth 80M
```

### 2. Custom Parameters
```bash
# Custom source, destination, duration, and bandwidth
python3 network/traffic/traffic_generator.py \
    --scenario tcp \
    --src h1 \
    --dst h4 \
    --duration 20

# Run in simulation / dry-run mode (does not require iperf3 binary)
python3 network/traffic/traffic_generator.py --scenario congestion --dry-run
```

### 3. Log Output
All scenario execution metadata and flow performance metrics are automatically written to:
- Structured JSON: `data/traffic_logs/<scenario>_<timestamp>.json`
- Human-Readable Report: `data/traffic_logs/<scenario>_<timestamp>.log`
