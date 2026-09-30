#ifndef CONTROL_LOGGER_H
#define CONTROL_LOGGER_H

#include <stdbool.h>
#include <stdint.h>
#include "control_config.h"

typedef struct {
    char timestamp[64];
    char device_id[MAX_DEVICE_LEN];
    char flow_id[MAX_FLOW_ID_LEN];
    char src_ip[MAX_IP_LEN];
    char dst_ip[MAX_IP_LEN];
    uint16_t src_port;
    uint16_t dst_port;
    char protocol[16];
    char traffic_class[32];
    char predicted_congestion_class[16];
    char final_priority[16];
    char action[16];        /* APPLY, UPDATE, REMOVE, RESET */
    char target_class[16];  /* 1:10, 1:20, 1:30, 1:40 */
    char interface[MAX_IFACE_LEN];
    bool dry_run;
    char status[16];        /* SUCCESS, FAILED, SKIPPED, DRY_RUN */
    char rule_identifier[MAX_RULE_ID_LEN];
    char error_message[MAX_ERR_MSG_LEN];
} control_log_entry_t;

/* State record structure */
typedef struct {
    char timestamp[64];
    char device_id[MAX_DEVICE_LEN];
    char flow_id[MAX_FLOW_ID_LEN];
    char interface[MAX_IFACE_LEN];
    char priority[16];
    char traffic_class[32];
    char control_class[16];
    char action[16];
    char status[16];
    char rule_identifier[MAX_RULE_ID_LEN];
    bool dry_run;
    char error_message[MAX_ERR_MSG_LEN];
} control_state_entry_t;

/* Logger Lifecycle & Methods */
bool init_control_logger(const char *actions_csv_path, const char *state_csv_path);
void close_control_logger(void);

bool log_control_action(const control_log_entry_t *entry);
bool record_control_state(const control_state_entry_t *entry);

void get_current_iso_timestamp(char *out_buf, size_t max_len);

#endif /* CONTROL_LOGGER_H */
