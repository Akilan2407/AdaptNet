#ifndef RECORD_PARSER_H
#define RECORD_PARSER_H

#include <stddef.h>
#include <stdint.h>
#include <netinet/in.h>

#define MAX_TIMESTAMP_STR 32
#define MAX_DEVICE_NAME 64
#define MAX_IP_STR INET_ADDRSTRLEN
#define MAX_PROTO_STR 8

/* Native C data structure for a validated network flow record */
typedef struct {
    char measurement_timestamp[MAX_TIMESTAMP_STR];
    char ingestion_timestamp[MAX_TIMESTAMP_STR];
    char device_id[MAX_DEVICE_NAME];
    char src_ip[MAX_IP_STR];
    char dst_ip[MAX_IP_STR];
    int src_port;
    int dst_port;
    char protocol[MAX_PROTO_STR]; /* "TCP" or "UDP" */
    double throughput_mbps;
    int has_rtt;                  /* 1 = measured, 0 = N/A */
    double rtt_ms;
    int has_packet_loss;          /* 1 = measured, 0 = N/A */
    double packet_loss_pct;
    int active_connections;
} NetworkRecord;

/* Helper to get current wall-clock ingestion timestamp */
void get_current_ingestion_timestamp(char *buf, size_t max_len);

/*
 * Parse a pipe-delimited raw line into a NetworkRecord.
 * Returns 0 on successful parse, -1 on parsing/tokenization error.
 */
int parse_network_record(const char *raw_line, NetworkRecord *out_record, char *error_msg, size_t error_len);

#endif /* RECORD_PARSER_H */
