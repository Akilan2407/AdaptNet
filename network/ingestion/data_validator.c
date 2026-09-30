#include "data_validator.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <arpa/inet.h>

static int is_valid_ipv4(const char *ip_str) {
    if (!ip_str || ip_str[0] == '\0') return 0;
    struct sockaddr_in sa;
    return (inet_pton(AF_INET, ip_str, &(sa.sin_addr)) == 1);
}

int validate_network_record(NetworkRecord *record, char *error_msg, size_t error_len) {
    if (!record) {
        if (error_msg) snprintf(error_msg, error_len, "Null record pointer");
        return 0;
    }

    /* 1. Timestamp */
    if (record->measurement_timestamp[0] == '\0' || strlen(record->measurement_timestamp) < 5) {
        if (error_msg) snprintf(error_msg, error_len, "Invalid or empty measurement timestamp");
        return 0;
    }

    /* 2. Device ID */
    if (record->device_id[0] == '\0') {
        if (error_msg) snprintf(error_msg, error_len, "Empty device ID");
        return 0;
    }

    /* 3. Source & Destination IP addresses */
    if (!is_valid_ipv4(record->src_ip)) {
        if (error_msg) snprintf(error_msg, error_len, "Invalid source IP format: '%s'", record->src_ip);
        return 0;
    }
    if (!is_valid_ipv4(record->dst_ip)) {
        if (error_msg) snprintf(error_msg, error_len, "Invalid destination IP format: '%s'", record->dst_ip);
        return 0;
    }

    /* 4. Port ranges (1 to 65535) */
    if (record->src_port < 1 || record->src_port > 65535) {
        if (error_msg) snprintf(error_msg, error_len, "Invalid source port %d (must be 1-65535)", record->src_port);
        return 0;
    }
    if (record->dst_port < 1 || record->dst_port > 65535) {
        if (error_msg) snprintf(error_msg, error_len, "Invalid destination port %d (must be 1-65535)", record->dst_port);
        return 0;
    }

    /* 5. Protocol */
    if (strcasecmp(record->protocol, "TCP") == 0) {
        snprintf(record->protocol, sizeof(record->protocol), "TCP");
    } else if (strcasecmp(record->protocol, "UDP") == 0) {
        snprintf(record->protocol, sizeof(record->protocol), "UDP");
    } else {
        if (error_msg) snprintf(error_msg, error_len, "Invalid protocol '%s' (must be TCP or UDP)", record->protocol);
        return 0;
    }

    /* 6. Throughput */
    if (record->throughput_mbps < 0.0) {
        if (error_msg) snprintf(error_msg, error_len, "Negative throughput: %.2f Mbps", record->throughput_mbps);
        return 0;
    }

    /* 7. RTT */
    if (record->has_rtt && record->rtt_ms < 0.0) {
        if (error_msg) snprintf(error_msg, error_len, "Negative RTT value: %.2f ms", record->rtt_ms);
        return 0;
    }

    /* 8. Packet Loss */
    if (record->has_packet_loss) {
        if (record->packet_loss_pct < 0.0 || record->packet_loss_pct > 100.0) {
            if (error_msg) snprintf(error_msg, error_len, "Invalid packet loss percentage: %.2f%% (must be 0-100)", record->packet_loss_pct);
            return 0;
        }
    }

    /* 9. Active Connections */
    if (record->active_connections < 0) {
        if (error_msg) snprintf(error_msg, error_len, "Negative active connections: %d", record->active_connections);
        return 0;
    }

    return 1;
}
