#ifndef NETWORK_STATS_H
#define NETWORK_STATS_H

#include <stdint.h>
#include <stddef.h>
#include <time.h>

#define MAX_IFACE_NAME 32
#define MAX_TIMESTAMP_LEN 32

/* Snapshot of network interface packet & byte counters */
typedef struct {
    char iface[MAX_IFACE_NAME];
    uint64_t rx_bytes;
    uint64_t tx_bytes;
    uint64_t rx_packets;
    uint64_t tx_packets;
    uint64_t rx_errors;
    uint64_t tx_errors;
    uint64_t rx_dropped;
    uint64_t tx_dropped;
    struct timespec ts;
} interface_stats_t;

/* Query current interface statistics from OS (/proc/net/dev or getifaddrs) */
int get_interface_stats(const char *iface_name, interface_stats_t *stats);

/* Calculate throughput in Megabits per second (Mbps) */
double calculate_throughput_mbps(uint64_t bytes_delta, double interval_seconds);

/* Format current system timestamp into human-readable buffer (YYYY-MM-DD HH:MM:SS) */
void get_current_timestamp_str(char *buf, size_t max_len);

/* Format epoch timestamp in milliseconds */
uint64_t get_current_timestamp_ms(void);

#endif /* NETWORK_STATS_H */
