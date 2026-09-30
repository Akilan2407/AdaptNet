#ifndef CONTROL_INTERFACE_H
#define CONTROL_INTERFACE_H

#include <stdbool.h>
#include <stdint.h>
#include "control_config.h"
#include "flow_mapper.h"
#include "tc_manager.h"

typedef enum {
    CMD_APPLY  = 0,
    CMD_REMOVE = 1,
    CMD_UPDATE = 2,
    CMD_STATUS = 3,
    CMD_RESET  = 4,
    CMD_UNKNOWN = -1
} control_cmd_type_t;

typedef enum {
    SCOPE_FLOW   = 0,
    SCOPE_DEVICE = 1
} control_scope_t;

typedef enum {
    CTRL_STATUS_SUCCESS = 0,
    CTRL_STATUS_FAILED  = 1,
    CTRL_STATUS_SKIPPED = 2,
    CTRL_STATUS_DRY_RUN = 3
} control_status_t;

typedef struct {
    control_cmd_type_t command;
    char device_id[MAX_DEVICE_LEN];
    char flow_id[MAX_FLOW_ID_LEN];
    char src_ip[MAX_IP_LEN];
    char dst_ip[MAX_IP_LEN];
    uint16_t src_port;
    uint16_t dst_port;
    char protocol[16];
    char traffic_class[32];
    char predicted_congestion_class[16];
    priority_level_t priority;
    control_scope_t requested_scope;
    char interface[MAX_IFACE_LEN];
    bool dry_run;
} control_request_t;

typedef struct {
    control_status_t status;
    char status_str[16];
    char rule_identifier[MAX_RULE_ID_LEN];
    char target_class[16];
    char executed_command[MAX_CMD_LEN];
    char error_message[MAX_ERR_MSG_LEN];
} control_response_t;

/* Core Dispatcher API */
bool init_control_subsystem(bool dry_run);
void shutdown_control_subsystem(void);

bool dispatch_control_request(
    const control_request_t *req,
    control_response_t *resp
);

/* Helper String Conversions */
control_cmd_type_t parse_command_type(const char *cmd_str);
const char* command_type_to_string(control_cmd_type_t cmd);
const char* control_status_to_string(control_status_t status);

#endif /* CONTROL_INTERFACE_H */
