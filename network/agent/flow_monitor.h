#ifndef FLOW_MONITOR_H
#define FLOW_MONITOR_H

#include <stdint.h>
#include <stddef.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define MAX_FLOWS_PER_SAMPLE 64
#define MAX_IP_STR_LEN INET_ADDRSTRLEN
#define MAX_PROTO_STR_LEN 8
#define MAX_DEVICE_ID_LEN 64

/* Structured metadata record for a single detected network flow */
typedef struct {
    char timestamp[32];
    char device_id[MAX_DEVICE_ID_LEN];
    char src_ip[MAX_IP_STR_LEN];
    char dst_ip[MAX_IP_STR_LEN];
    uint16_t src_port;
    uint16_t dst_port;
    char protocol[MAX_PROTO_STR_LEN];  /* "TCP" or "UDP" */
    double throughput_mbps;
    int has_rtt;                       /* 1 = valid RTT, 0 = N/A */
    double rtt_ms;
    int has_packet_loss;               /* 1 = valid packet loss, 0 = N/A */
    double packet_loss_pct;
    int active_tcp_connections;
    int active_udp_connections;
    int total_active_connections;
} flow_record_t;

/*
 * Scan active TCP and UDP flows from kernel network tables.
 * Populates flows array up to max_flows and counts active sockets.
 * Returns number of flow records captured.
 */
int scan_active_flows(
    const char *device_id,
    double current_throughput,
    flow_record_t *flows,
    int max_flows,
    int *out_tcp_count,
    int *out_udp_count
);

#endif /* FLOW_MONITOR_H */
