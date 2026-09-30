#include "flow_mapper.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

bool is_valid_ipv4(const char *ip) {
    if (!ip || strlen(ip) == 0 || strlen(ip) > 15) return false;
    int a, b, c, d;
    char tail[2];
    tail[0] = '\0';
    if (sscanf(ip, "%d.%d.%d.%d%1s", &a, &b, &c, &d, tail) != 4) {
        return false;
    }
    if (tail[0] != '\0') return false;
    if (a < 0 || a > 255 || b < 0 || b > 255 ||
        c < 0 || c > 255 || d < 0 || d > 255) {
        return false;
    }
    return true;
}

bool is_valid_port(int port) {
    return (port >= 1 && port <= 65535);
}

bool is_valid_protocol(const char *proto) {
    if (!proto) return false;
    if (strcasecmp(proto, "TCP") == 0 || strcasecmp(proto, "UDP") == 0) {
        return true;
    }
    return false;
}

bool is_allowlisted_interface(const char *iface) {
    if (!iface || strlen(iface) == 0) return false;
    for (int i = 0; ALLOWLISTED_INTERFACES[i] != NULL; i++) {
        if (strcmp(ALLOWLISTED_INTERFACES[i], iface) == 0) {
            return true;
        }
    }
    return false;
}

bool is_known_device(const char *device_id) {
    if (!device_id || strlen(device_id) == 0) return false;
    for (int i = 0; KNOWN_DEVICES[i] != NULL; i++) {
        if (strcmp(KNOWN_DEVICES[i], device_id) == 0) {
            return true;
        }
    }
    return false;
}

bool resolve_device_interface(const char *device_id, char *out_interface, size_t max_len) {
    if (!device_id || !out_interface || max_len == 0) return false;

    if (device_id[0] == 'h' && isdigit(device_id[1])) {
        int host_num = atoi(&device_id[1]);
        if (host_num >= 1 && host_num <= 5) {
            snprintf(out_interface, max_len, "s1-eth%d", host_num);
            return true;
        }
    }
    // Fallback if already an interface name
    if (is_allowlisted_interface(device_id)) {
        snprintf(out_interface, max_len, "%s", device_id);
        return true;
    }
    return false;
}

bool resolve_device_ip(const char *device_id, char *out_ip, size_t max_len) {
    if (!device_id || !out_ip || max_len == 0) return false;

    if (device_id[0] == 'h' && isdigit(device_id[1])) {
        int host_num = atoi(&device_id[1]);
        if (host_num >= 1 && host_num <= 50) {
            snprintf(out_ip, max_len, "192.168.1.%d", 9 + host_num);
            return true;
        }
    }
    return false;
}

bool parse_flow_id(const char *flow_id, flow_tuple_t *tuple) {
    if (!flow_id || !tuple) return false;
    memset(tuple, 0, sizeof(flow_tuple_t));

    // Expected format: <device>_<src_ip>:<src_port>-><dst_ip>:<dst_port>_<proto>
    // e.g.: h1_192.168.1.10:45672->192.168.1.11:5201_TCP
    char temp[MAX_FLOW_ID_LEN * 2];
    strncpy(temp, flow_id, sizeof(temp) - 1);
    temp[sizeof(temp) - 1] = '\0';

    char *dev_sep = strchr(temp, '_');
    if (!dev_sep) return false;
    *dev_sep = '\0';
    strncpy(tuple->device_id, temp, sizeof(tuple->device_id) - 1);

    char *remainder = dev_sep + 1;
    char *arrow = strstr(remainder, "->");
    if (!arrow) return false;
    *arrow = '\0';

    // Parse src_ip:src_port
    char *src_part = remainder;
    char *src_colon = strchr(src_part, ':');
    if (!src_colon) return false;
    *src_colon = '\0';
    strncpy(tuple->src_ip, src_part, sizeof(tuple->src_ip) - 1);
    tuple->src_port = (uint16_t)atoi(src_colon + 1);

    // Parse dst_ip:dst_port_proto
    char *dst_part = arrow + 2;
    char *proto_sep = strrchr(dst_part, '_');
    if (!proto_sep) return false;
    *proto_sep = '\0';
    strncpy(tuple->protocol, proto_sep + 1, sizeof(tuple->protocol) - 1);

    char *dst_colon = strchr(dst_part, ':');
    if (!dst_colon) return false;
    *dst_colon = '\0';
    strncpy(tuple->dst_ip, dst_part, sizeof(tuple->dst_ip) - 1);
    tuple->dst_port = (uint16_t)atoi(dst_colon + 1);

    // Resolve interface
    resolve_device_interface(tuple->device_id, tuple->interface, sizeof(tuple->interface));

    // Validate
    if (!is_valid_ipv4(tuple->src_ip) || !is_valid_ipv4(tuple->dst_ip)) {
        return false;
    }
    if (!is_valid_port(tuple->src_port) || !is_valid_port(tuple->dst_port)) {
        return false;
    }
    if (!is_valid_protocol(tuple->protocol)) {
        return false;
    }

    return true;
}
