#include "record_parser.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <ctype.h>

void get_current_ingestion_timestamp(char *buf, size_t max_len) {
    if (!buf || max_len == 0) return;
    time_t rawtime;
    struct tm timeinfo;
    time(&rawtime);
    localtime_r(&rawtime, &timeinfo);
    strftime(buf, max_len, "%Y-%m-%d %H:%M:%S", &timeinfo);
}

static void trim_whitespace(char *str) {
    if (!str) return;
    char *p = str;
    while (*p && isspace((unsigned char)*p)) p++;
    if (p != str) memmove(str, p, strlen(p) + 1);

    size_t len = strlen(str);
    while (len > 0 && isspace((unsigned char)str[len - 1])) {
        str[len - 1] = '\0';
        len--;
    }
}

int parse_network_record(const char *raw_line, NetworkRecord *out_record, char *error_msg, size_t error_len) {
    if (!raw_line || !out_record) {
        if (error_msg) snprintf(error_msg, error_len, "Null input or record pointer");
        return -1;
    }

    memset(out_record, 0, sizeof(NetworkRecord));

    char line_buf[1024];
    snprintf(line_buf, sizeof(line_buf), "%s", raw_line);
    trim_whitespace(line_buf);

    if (line_buf[0] == '\0') {
        if (error_msg) snprintf(error_msg, error_len, "Empty record line");
        return -1;
    }

    /*
     * Schema:
     * 0: timestamp
     * 1: device_id
     * 2: src_ip
     * 3: dst_ip
     * 4: src_port
     * 5: dst_port
     * 6: protocol
     * 7: throughput
     * 8: rtt
     * 9: packet_loss
     * 10: active_connections
     */
    char *tokens[16];
    int count = 0;
    char *saveptr = NULL;
    char *tok = strtok_r(line_buf, "|", &saveptr);

    while (tok && count < 16) {
        tokens[count++] = tok;
        tok = strtok_r(NULL, "|", &saveptr);
    }

    if (count != 11) {
        if (error_msg) {
            snprintf(error_msg, error_len, "Invalid field count: expected 11 fields, found %d", count);
        }
        return -1;
    }

    /* Timestamps */
    snprintf(out_record->measurement_timestamp, sizeof(out_record->measurement_timestamp), "%s", tokens[0]);
    get_current_ingestion_timestamp(out_record->ingestion_timestamp, sizeof(out_record->ingestion_timestamp));

    /* Identifiers & Endpoints */
    snprintf(out_record->device_id, sizeof(out_record->device_id), "%s", tokens[1]);
    snprintf(out_record->src_ip, sizeof(out_record->src_ip), "%s", tokens[2]);
    snprintf(out_record->dst_ip, sizeof(out_record->dst_ip), "%s", tokens[3]);

    /* Numeric Ports */
    out_record->src_port = atoi(tokens[4]);
    out_record->dst_port = atoi(tokens[5]);

    /* Protocol */
    snprintf(out_record->protocol, sizeof(out_record->protocol), "%s", tokens[6]);

    /* Throughput */
    out_record->throughput_mbps = atof(tokens[7]);

    /* RTT */
    if (strcasecmp(tokens[8], "N/A") == 0 || tokens[8][0] == '\0') {
        out_record->has_rtt = 0;
        out_record->rtt_ms = 0.0;
    } else {
        out_record->has_rtt = 1;
        out_record->rtt_ms = atof(tokens[8]);
    }

    /* Packet Loss */
    if (strcasecmp(tokens[9], "N/A") == 0 || tokens[9][0] == '\0') {
        out_record->has_packet_loss = 0;
        out_record->packet_loss_pct = 0.0;
    } else {
        out_record->has_packet_loss = 1;
        out_record->packet_loss_pct = atof(tokens[9]);
    }

    /* Active Connections */
    out_record->active_connections = atoi(tokens[10]);

    return 0;
}
