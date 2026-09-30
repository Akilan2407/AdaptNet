# Network Data Ingestion Module (Phase 6)

## 1. Purpose
The **Network Data Ingestion Module** receives raw stream lines from the multi-threaded **C Network Controller** (over TCP sockets), performs strict schema and semantic validation, filters out duplicates, buffers the most recent records in memory, and writes structured outputs to persistent CSV and JSONL storage for downstream Phase 7 Feature Extraction and ML training.

---

## 2. Ingestion Architecture & Pipeline

```
Raw Socket Stream (TCP)
          │
          ▼
┌──────────────────┐
│  Record Parser   │ ──> Tokenizes pipe-delimited line & converts to native numeric types
└─────────┬────────┘
          │
          ▼
┌──────────────────┐
│  Data Validator  │ ──> Verifies 11 fields, IPv4 format, ports (1-65535), protocol & non-negative metrics
└─────────┬────────┘
          │
    [Is Valid?] ──────(No)───> [Log to invalid_records.log with rejection reason]
          │ (Yes)
          ▼
┌──────────────────┐
│ Duplicate Check  │ ──> Inspects recent buffer for identical 5-tuple + timestamp records
└─────────┬────────┘
          │
    [Is Duplicate?] ──(Yes)──> [Log duplicate event to invalid_records.log]
          │ (No)
          ▼
┌────────────────────────────────────────────────────────┐
│                      Data Store                        │
│  ├── In-Memory Circular Ring Buffer (default: 1000)    │
│  ├── Device Tracking Engine (counts, protocols, ts)    │
│  ├── CSV Storage: data/monitoring/network_metrics.csv  │
│  └── JSONL Storage: data/monitoring/network_metrics.jsonl
└────────────────────────────────────────────────────────┘
```

---

## 3. Input Protocol & Record Structure

### Wire Format (11 Fields)
```
timestamp|device_id|src_ip|dst_ip|src_port|dst_port|protocol|throughput|rtt|packet_loss|active_connections\n
```

### Native C `NetworkRecord` Representation
```c
typedef struct {
    char measurement_timestamp[32]; // Originating timestamp from agent
    char ingestion_timestamp[32];   // Controller ingestion timestamp
    char device_id[64];             // Host identifier (h1, h2, ...)
    char src_ip[16];                // Dotted IPv4
    char dst_ip[16];                // Dotted IPv4
    int src_port;                   // 1 to 65535
    int dst_port;                   // 1 to 65535
    char protocol[8];               // "TCP" or "UDP"
    double throughput_mbps;         // Megabits per second
    int has_rtt;                    // 1 if measured, 0 if N/A
    double rtt_ms;                  // Latency in ms
    int has_packet_loss;            // 1 if measured, 0 if N/A
    double packet_loss_pct;         // Loss percentage (0-100)
    int active_connections;         // Concurrent active socket count
} NetworkRecord;
```

---

## 4. Validation Rules & Rejection Handling

| Metric / Field | Validation Rule | Rejection Reason |
| :--- | :--- | :--- |
| **Field Count** | Exactly 11 non-empty pipe-delimited tokens | `Invalid field count: expected 11 fields` |
| **Timestamp** | Non-empty string (length $\ge 5$) | `Invalid or empty measurement timestamp` |
| **Device ID** | Non-empty string | `Empty device ID` |
| **IP Addresses**| Valid IPv4 format (`inet_pton`) | `Invalid source/destination IP format` |
| **Ports** | Integer in $[1, 65535]$ | `Invalid source/destination port (must be 1-65535)` |
| **Protocol** | Case-insensitive `"TCP"` or `"UDP"` | `Invalid protocol (must be TCP or UDP)` |
| **Throughput** | Float $\ge 0.0$ Mbps | `Negative throughput` |
| **RTT** | Float $\ge 0.0$ ms (or `"N/A"`) | `Negative RTT value` |
| **Packet Loss**| Float in $[0.0, 100.0]$ (or `"N/A"`) | `Invalid packet loss percentage (must be 0-100)` |
| **Connections**| Integer $\ge 0$ | `Negative active connections` |

Rejected records are logged to `data/monitoring/invalid_records.log`:
```
[2026-09-12 15:20:01] REJECTED (Invalid destination port 99999): 2026-09-12 15:20:01|h1|10.0.0.1|10.0.0.2|45120|99999|TCP|12.45|2.31|N/A|1
```

---

## 5. Deduplication & Circular Ring Buffer

### Deduplication Strategy
A flow record is flagged as a duplicate if an identical tuple `(measurement_timestamp, device_id, src_ip, dst_ip, src_port, dst_port, protocol)` was already ingested into the recent buffer within the current time slice.

### Circular Ring Buffer
- **Default Capacity**: 1000 records (`--buffer-size 1000`).
- **Behavior**: Constant $O(1)$ insertions. When the buffer reaches capacity, new records overwrite the oldest entries in circular fashion.
- **Phase 7 Access**: Provides low-latency memory access to recent network flows for windowed feature extraction.

---

## 6. Persistent Storage Outputs

### A. CSV Dataset (`data/monitoring/network_metrics.csv`)
```csv
timestamp,device_id,src_ip,dst_ip,src_port,dst_port,protocol,throughput,rtt,packet_loss,active_connections
2026-09-12 15:20:01,h1,192.168.1.10,192.168.1.11,45120,5201,TCP,12.45,2.31,N/A,1
2026-09-12 15:20:02,h2,192.168.1.11,192.168.1.12,45672,5201,TCP,94.50,N/A,N/A,1
2026-09-12 15:20:02,h3,192.168.1.12,192.168.1.13,45672,5202,UDP,10.00,N/A,N/A,1
```

### B. JSON Lines Dataset (`data/monitoring/network_metrics.jsonl`)
```json
{"timestamp":"2026-09-12 15:20:01","ingestion_timestamp":"2026-09-12 15:20:02","device_id":"h1","src_ip":"192.168.1.10","dst_ip":"192.168.1.11","src_port":45120,"dst_port":5201,"protocol":"TCP","throughput":12.45,"rtt":2.31,"packet_loss":null,"active_connections":1}
```

---

## 7. Thread Safety & Mutex Locking
The ingestion pipeline is designed for multi-client concurrent streaming:
- A dedicated `pthread_mutex_t` protects the circular ring buffer, statistics counters, device tracking tables, and file write handles.
- Prevents race conditions and guarantees atomicity of CSV/JSONL records across simultaneous agent threads.
