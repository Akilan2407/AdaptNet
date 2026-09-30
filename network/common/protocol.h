#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

#define PROTOCOL_MAGIC 0x4E544D31 /* "NTM1" - Network Traffic Management v1 */
#define DEFAULT_AGENT_PORT 9090
#define DEFAULT_CONTROLLER_PORT 9091
#define MAX_HOST_ID_LEN 64

/* Message Types between Agent <-> Controller */
typedef enum {
    MSG_TYPE_HEARTBEAT       = 0x01,
    MSG_TYPE_METRICS_REPORT  = 0x02,
    MSG_TYPE_CONGESTION_ALERT= 0x03,
    MSG_TYPE_POLICY_UPDATE   = 0x04,
    MSG_TYPE_ACK             = 0x05,
    MSG_TYPE_ERROR           = 0xFF
} message_type_t;

/* Monitored Protocol Classification */
typedef enum {
    TRAFFIC_PROTO_UNKNOWN = 0,
    TRAFFIC_PROTO_TCP     = 6,
    TRAFFIC_PROTO_UDP     = 17
} traffic_protocol_t;

/* Fixed-size Header for all TCP IPC Frames */
#pragma pack(push, 1)
typedef struct {
    uint32_t magic;           /* PROTOCOL_MAGIC */
    uint16_t version;         /* Protocol version (e.g., 1) */
    uint16_t msg_type;        /* message_type_t */
    uint32_t payload_length;  /* Length of payload following header */
    uint64_t timestamp_ms;    /* Unix epoch timestamp in milliseconds */
} packet_header_t;

/* Telemetry payload reported by C monitoring agents */
typedef struct {
    char host_id[MAX_HOST_ID_LEN];
    uint32_t src_ip;
    uint32_t dst_ip;
    uint16_t src_port;
    uint16_t dst_port;
    uint8_t  protocol;        /* traffic_protocol_t (TCP/UDP) */
    uint64_t bytes_sent;
    uint64_t bytes_received;
    uint64_t packets_sent;
    uint64_t packets_received;
    float    rtt_ms;
    float    jitter_ms;
    float    packet_loss_rate;
} telemetry_metric_t;
#pragma pack(pop)

#endif /* PROTOCOL_H */
