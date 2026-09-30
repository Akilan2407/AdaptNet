#ifndef FLOW_MAPPER_H
#define FLOW_MAPPER_H

#include <stdbool.h>
#include <stdint.h>
#include "control_config.h"

typedef struct {
    char device_id[MAX_DEVICE_LEN];
    char src_ip[MAX_IP_LEN];
    char dst_ip[MAX_IP_LEN];
    uint16_t src_port;
    uint16_t dst_port;
    char protocol[16];
    char interface[MAX_IFACE_LEN];
} flow_tuple_t;

/* Parsing & Resolution */
bool parse_flow_id(const char *flow_id, flow_tuple_t *tuple);
bool resolve_device_interface(const char *device_id, char *out_interface, size_t max_len);
bool resolve_device_ip(const char *device_id, char *out_ip, size_t max_len);

/* Sanitization & Validation */
bool is_valid_ipv4(const char *ip);
bool is_valid_port(int port);
bool is_valid_protocol(const char *proto);
bool is_allowlisted_interface(const char *iface);
bool is_known_device(const char *device_id);

#endif /* FLOW_MAPPER_H */
