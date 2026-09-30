#include "control_interface.h"
#include "control_logger.h"
#include "flow_mapper.h"
#include "rollback.h"
#include "tc_manager.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <pthread.h>

#define MAX_ACTIVE_RULES 256

typedef struct {
    char flow_id[MAX_FLOW_ID_LEN];
    char interface[MAX_IFACE_LEN];
    priority_level_t priority;
    uint32_t filter_handle;
    char target_class[16];
    char rule_id[MAX_RULE_ID_LEN];
    bool active;
} active_rule_t;

static active_rule_t rule_table[MAX_ACTIVE_RULES];
static size_t rule_count = 0;
static uint32_t next_filter_id = 0x100;
static pthread_mutex_t interface_mutex = PTHREAD_MUTEX_INITIALIZER;
static bool subsystem_ready = false;

control_cmd_type_t parse_command_type(const char *cmd_str) {
    if (!cmd_str) return CMD_UNKNOWN;
    if (strcasecmp(cmd_str, "APPLY") == 0)  return CMD_APPLY;
    if (strcasecmp(cmd_str, "REMOVE") == 0) return CMD_REMOVE;
    if (strcasecmp(cmd_str, "UPDATE") == 0) return CMD_UPDATE;
    if (strcasecmp(cmd_str, "STATUS") == 0) return CMD_STATUS;
    if (strcasecmp(cmd_str, "RESET") == 0 || strcasecmp(cmd_str, "ROLLBACK") == 0) return CMD_RESET;
    return CMD_UNKNOWN;
}

const char* command_type_to_string(control_cmd_type_t cmd) {
    switch (cmd) {
        case CMD_APPLY:  return "APPLY";
        case CMD_REMOVE: return "REMOVE";
        case CMD_UPDATE: return "UPDATE";
        case CMD_STATUS: return "STATUS";
        case CMD_RESET:  return "RESET";
        default:         return "UNKNOWN";
    }
}

const char* control_status_to_string(control_status_t status) {
    switch (status) {
        case CTRL_STATUS_SUCCESS: return "SUCCESS";
        case CTRL_STATUS_FAILED:  return "FAILED";
        case CTRL_STATUS_SKIPPED: return "SKIPPED";
        case CTRL_STATUS_DRY_RUN: return "DRY_RUN";
        default:                  return "UNKNOWN";
    }
}

bool init_control_subsystem(bool dry_run) {
    pthread_mutex_lock(&interface_mutex);
    memset(rule_table, 0, sizeof(rule_table));
    rule_count = 0;
    next_filter_id = 0x100;
    init_control_logger(DEFAULT_CONTROL_ACTIONS_CSV, DEFAULT_CONTROL_STATE_CSV);
    subsystem_ready = true;
    (void)dry_run;
    pthread_mutex_unlock(&interface_mutex);
    return true;
}

void shutdown_control_subsystem(void) {
    pthread_mutex_lock(&interface_mutex);
    close_control_logger();
    subsystem_ready = false;
    pthread_mutex_unlock(&interface_mutex);
}

static int find_rule_index(const char *flow_id) {
    if (!flow_id) return -1;
    for (size_t i = 0; i < rule_count; i++) {
        if (rule_table[i].active && strcmp(rule_table[i].flow_id, flow_id) == 0) {
            return (int)i;
        }
    }
    return -1;
}

bool dispatch_control_request(
    const control_request_t *req,
    control_response_t *resp
) {
    if (!req || !resp) return false;
    pthread_mutex_lock(&interface_mutex);
    if (!subsystem_ready) {
        init_control_subsystem(req->dry_run);
    }

    memset(resp, 0, sizeof(control_response_t));

    // Handle RESET / ROLLBACK command directly
    if (req->command == CMD_RESET) {
        char err_buf[MAX_ERR_MSG_LEN] = {0};
        int rolled_back = rollback_all(req->dry_run, err_buf, sizeof(err_buf));
        for (size_t i = 0; i < rule_count; i++) {
            rule_table[i].active = false;
        }
        rule_count = 0;

        resp->status = req->dry_run ? CTRL_STATUS_DRY_RUN : CTRL_STATUS_SUCCESS;
        strncpy(resp->status_str, control_status_to_string(resp->status), sizeof(resp->status_str) - 1);
        snprintf(resp->rule_identifier, sizeof(resp->rule_identifier), "all_interfaces_reset");
        snprintf(resp->executed_command, sizeof(resp->executed_command), "rollback_all(%d interfaces)", rolled_back);

        pthread_mutex_unlock(&interface_mutex);
        return true;
    }

    // 1. Validate Input Parameters (Safety Requirement)
    if (!is_known_device(req->device_id)) {
        resp->status = CTRL_STATUS_FAILED;
        strncpy(resp->status_str, "FAILED", sizeof(resp->status_str) - 1);
        snprintf(resp->error_message, sizeof(resp->error_message), "Unknown device_id '%s'", req->device_id);

        control_log_entry_t err_log = {0};
        strncpy(err_log.device_id, req->device_id, sizeof(err_log.device_id) - 1);
        strncpy(err_log.flow_id, req->flow_id, sizeof(err_log.flow_id) - 1);
        strncpy(err_log.action, command_type_to_string(req->command), sizeof(err_log.action) - 1);
        strncpy(err_log.status, "FAILED", sizeof(err_log.status) - 1);
        err_log.dry_run = req->dry_run;
        strncpy(err_log.error_message, resp->error_message, sizeof(err_log.error_message) - 1);
        log_control_action(&err_log);

        pthread_mutex_unlock(&interface_mutex);
        return false;
    }

    // Resolve interface if empty
    char iface[MAX_IFACE_LEN] = {0};
    if (req->interface[0] != '\0') {
        strncpy(iface, req->interface, sizeof(iface) - 1);
    } else {
        resolve_device_interface(req->device_id, iface, sizeof(iface));
    }

    if (!is_allowlisted_interface(iface)) {
        resp->status = CTRL_STATUS_FAILED;
        strncpy(resp->status_str, "FAILED", sizeof(resp->status_str) - 1);
        snprintf(resp->error_message, sizeof(resp->error_message), "Interface '%s' not allowlisted", iface);

        control_log_entry_t err_log = {0};
        strncpy(err_log.device_id, req->device_id, sizeof(err_log.device_id) - 1);
        strncpy(err_log.flow_id, req->flow_id, sizeof(err_log.flow_id) - 1);
        strncpy(err_log.action, command_type_to_string(req->command), sizeof(err_log.action) - 1);
        strncpy(err_log.status, "FAILED", sizeof(err_log.status) - 1);
        err_log.dry_run = req->dry_run;
        strncpy(err_log.error_message, resp->error_message, sizeof(err_log.error_message) - 1);
        log_control_action(&err_log);

        pthread_mutex_unlock(&interface_mutex);
        return false;
    }

    // Validate 5-tuple
    if (!is_valid_ipv4(req->src_ip) || !is_valid_ipv4(req->dst_ip) ||
        !is_valid_port(req->src_port) || !is_valid_port(req->dst_port) ||
        !is_valid_protocol(req->protocol)) {
        resp->status = CTRL_STATUS_FAILED;
        strncpy(resp->status_str, "FAILED", sizeof(resp->status_str) - 1);
        snprintf(resp->error_message, sizeof(resp->error_message),
                 "Invalid 5-tuple attributes (src=%s:%d, dst=%s:%d, proto=%s)",
                 req->src_ip, req->src_port, req->dst_ip, req->dst_port, req->protocol);

        control_log_entry_t err_log = {0};
        strncpy(err_log.device_id, req->device_id, sizeof(err_log.device_id) - 1);
        strncpy(err_log.flow_id, req->flow_id, sizeof(err_log.flow_id) - 1);
        strncpy(err_log.action, command_type_to_string(req->command), sizeof(err_log.action) - 1);
        strncpy(err_log.status, "FAILED", sizeof(err_log.status) - 1);
        err_log.dry_run = req->dry_run;
        strncpy(err_log.error_message, resp->error_message, sizeof(err_log.error_message) - 1);
        log_control_action(&err_log);

        pthread_mutex_unlock(&interface_mutex);
        return false;
    }

    // Validate priority
    if (req->priority == PRIO_LEVEL_UNKNOWN) {
        resp->status = CTRL_STATUS_FAILED;
        strncpy(resp->status_str, "FAILED", sizeof(resp->status_str) - 1);
        snprintf(resp->error_message, sizeof(resp->error_message), "Invalid priority level");

        control_log_entry_t err_log = {0};
        strncpy(err_log.device_id, req->device_id, sizeof(err_log.device_id) - 1);
        strncpy(err_log.flow_id, req->flow_id, sizeof(err_log.flow_id) - 1);
        strncpy(err_log.action, command_type_to_string(req->command), sizeof(err_log.action) - 1);
        strncpy(err_log.status, "FAILED", sizeof(err_log.status) - 1);
        err_log.dry_run = req->dry_run;
        strncpy(err_log.error_message, resp->error_message, sizeof(err_log.error_message) - 1);
        log_control_action(&err_log);

        pthread_mutex_unlock(&interface_mutex);
        return false;
    }

    const char *target_class = priority_to_tc_class(req->priority);
    strncpy(resp->target_class, target_class, sizeof(resp->target_class) - 1);

    // Build flow tuple for TC manager
    flow_tuple_t flow;
    memset(&flow, 0, sizeof(flow_tuple_t));
    strncpy(flow.device_id, req->device_id, sizeof(flow.device_id) - 1);
    strncpy(flow.src_ip, req->src_ip, sizeof(flow.src_ip) - 1);
    strncpy(flow.dst_ip, req->dst_ip, sizeof(flow.dst_ip) - 1);
    flow.src_port = req->src_port;
    flow.dst_port = req->dst_port;
    strncpy(flow.protocol, req->protocol, sizeof(flow.protocol) - 1);
    strncpy(flow.interface, iface, sizeof(flow.interface) - 1);

    int existing_idx = find_rule_index(req->flow_id);
    tc_operation_result_t tc_res = {0};

    // 2. Process Command Logic
    if (req->command == CMD_APPLY) {
        if (existing_idx >= 0) {
            // Flow already exists. Check if priority changed -> convert to UPDATE
            if (rule_table[existing_idx].priority == req->priority) {
                // Duplicate rule with identical priority: skip to avoid duplicates
                resp->status = CTRL_STATUS_SKIPPED;
                strncpy(resp->status_str, "SKIPPED", sizeof(resp->status_str) - 1);
                strncpy(resp->rule_identifier, rule_table[existing_idx].rule_id, sizeof(resp->rule_identifier) - 1);
                snprintf(resp->error_message, sizeof(resp->error_message), "Identical rule already active");

                control_log_entry_t log_entry = {0};
                strncpy(log_entry.device_id, req->device_id, sizeof(log_entry.device_id) - 1);
                strncpy(log_entry.flow_id, req->flow_id, sizeof(log_entry.flow_id) - 1);
                strncpy(log_entry.src_ip, req->src_ip, sizeof(log_entry.src_ip) - 1);
                strncpy(log_entry.dst_ip, req->dst_ip, sizeof(log_entry.dst_ip) - 1);
                log_entry.src_port = req->src_port;
                log_entry.dst_port = req->dst_port;
                strncpy(log_entry.protocol, req->protocol, sizeof(log_entry.protocol) - 1);
                strncpy(log_entry.traffic_class, req->traffic_class, sizeof(log_entry.traffic_class) - 1);
                strncpy(log_entry.predicted_congestion_class, req->predicted_congestion_class, sizeof(log_entry.predicted_congestion_class) - 1);
                strncpy(log_entry.final_priority, target_class, sizeof(log_entry.final_priority) - 1);
                strncpy(log_entry.action, "APPLY", sizeof(log_entry.action) - 1);
                strncpy(log_entry.target_class, target_class, sizeof(log_entry.target_class) - 1);
                strncpy(log_entry.interface, iface, sizeof(log_entry.interface) - 1);
                log_entry.dry_run = req->dry_run;
                strncpy(log_entry.status, "SKIPPED", sizeof(log_entry.status) - 1);
                strncpy(log_entry.rule_identifier, resp->rule_identifier, sizeof(log_entry.rule_identifier) - 1);
                strncpy(log_entry.error_message, resp->error_message, sizeof(log_entry.error_message) - 1);
                log_control_action(&log_entry);

                pthread_mutex_unlock(&interface_mutex);
                return true;
            } else {
                // Priority updated: dynamically update existing filter
                uint32_t handle = rule_table[existing_idx].filter_handle;
                bool ok = tc_update_filter(iface, &flow, target_class, handle, req->dry_run, &tc_res);

                resp->status = req->dry_run ? CTRL_STATUS_DRY_RUN : (ok ? CTRL_STATUS_SUCCESS : CTRL_STATUS_FAILED);
                strncpy(resp->status_str, control_status_to_string(resp->status), sizeof(resp->status_str) - 1);
                strncpy(resp->rule_identifier, tc_res.rule_identifier, sizeof(resp->rule_identifier) - 1);
                strncpy(resp->executed_command, tc_res.generated_command, sizeof(resp->executed_command) - 1);
                strncpy(resp->error_message, tc_res.error_message, sizeof(resp->error_message) - 1);

                rule_table[existing_idx].priority = req->priority;
                strncpy(rule_table[existing_idx].target_class, target_class, sizeof(rule_table[existing_idx].target_class) - 1);

                control_log_entry_t log_entry = {0};
                strncpy(log_entry.device_id, req->device_id, sizeof(log_entry.device_id) - 1);
                strncpy(log_entry.flow_id, req->flow_id, sizeof(log_entry.flow_id) - 1);
                strncpy(log_entry.src_ip, req->src_ip, sizeof(log_entry.src_ip) - 1);
                strncpy(log_entry.dst_ip, req->dst_ip, sizeof(log_entry.dst_ip) - 1);
                log_entry.src_port = req->src_port;
                log_entry.dst_port = req->dst_port;
                strncpy(log_entry.protocol, req->protocol, sizeof(log_entry.protocol) - 1);
                strncpy(log_entry.traffic_class, req->traffic_class, sizeof(log_entry.traffic_class) - 1);
                strncpy(log_entry.predicted_congestion_class, req->predicted_congestion_class, sizeof(log_entry.predicted_congestion_class) - 1);
                snprintf(log_entry.final_priority, sizeof(log_entry.final_priority), "%s", target_class);
                strncpy(log_entry.action, "UPDATE", sizeof(log_entry.action) - 1);
                strncpy(log_entry.target_class, target_class, sizeof(log_entry.target_class) - 1);
                strncpy(log_entry.interface, iface, sizeof(log_entry.interface) - 1);
                log_entry.dry_run = req->dry_run;
                strncpy(log_entry.status, resp->status_str, sizeof(log_entry.status) - 1);
                strncpy(log_entry.rule_identifier, resp->rule_identifier, sizeof(log_entry.rule_identifier) - 1);
                strncpy(log_entry.error_message, resp->error_message, sizeof(log_entry.error_message) - 1);
                log_control_action(&log_entry);

                pthread_mutex_unlock(&interface_mutex);
                return ok;
            }
        } else {
            // New rule application
            register_managed_interface(iface);
            uint32_t handle = next_filter_id++;
            bool ok = tc_apply_filter(iface, &flow, target_class, handle, req->dry_run, &tc_res);

            resp->status = req->dry_run ? CTRL_STATUS_DRY_RUN : (ok ? CTRL_STATUS_SUCCESS : CTRL_STATUS_FAILED);
            strncpy(resp->status_str, control_status_to_string(resp->status), sizeof(resp->status_str) - 1);
            strncpy(resp->rule_identifier, tc_res.rule_identifier, sizeof(resp->rule_identifier) - 1);
            strncpy(resp->executed_command, tc_res.generated_command, sizeof(resp->executed_command) - 1);
            strncpy(resp->error_message, tc_res.error_message, sizeof(resp->error_message) - 1);

            if (rule_count < MAX_ACTIVE_RULES) {
                strncpy(rule_table[rule_count].flow_id, req->flow_id, sizeof(rule_table[rule_count].flow_id) - 1);
                strncpy(rule_table[rule_count].interface, iface, sizeof(rule_table[rule_count].interface) - 1);
                rule_table[rule_count].priority = req->priority;
                rule_table[rule_count].filter_handle = handle;
                strncpy(rule_table[rule_count].target_class, target_class, sizeof(rule_table[rule_count].target_class) - 1);
                strncpy(rule_table[rule_count].rule_id, resp->rule_identifier, sizeof(rule_table[rule_count].rule_id) - 1);
                rule_table[rule_count].active = true;
                rule_count++;
            }

            // Log action
            control_log_entry_t log_entry = {0};
            strncpy(log_entry.device_id, req->device_id, sizeof(log_entry.device_id) - 1);
            strncpy(log_entry.flow_id, req->flow_id, sizeof(log_entry.flow_id) - 1);
            strncpy(log_entry.src_ip, req->src_ip, sizeof(log_entry.src_ip) - 1);
            strncpy(log_entry.dst_ip, req->dst_ip, sizeof(log_entry.dst_ip) - 1);
            log_entry.src_port = req->src_port;
            log_entry.dst_port = req->dst_port;
            strncpy(log_entry.protocol, req->protocol, sizeof(log_entry.protocol) - 1);
            strncpy(log_entry.traffic_class, req->traffic_class, sizeof(log_entry.traffic_class) - 1);
            strncpy(log_entry.predicted_congestion_class, req->predicted_congestion_class, sizeof(log_entry.predicted_congestion_class) - 1);
            snprintf(log_entry.final_priority, sizeof(log_entry.final_priority), "%s", target_class);
            strncpy(log_entry.action, "APPLY", sizeof(log_entry.action) - 1);
            strncpy(log_entry.target_class, target_class, sizeof(log_entry.target_class) - 1);
            strncpy(log_entry.interface, iface, sizeof(log_entry.interface) - 1);
            log_entry.dry_run = req->dry_run;
            strncpy(log_entry.status, resp->status_str, sizeof(log_entry.status) - 1);
            strncpy(log_entry.rule_identifier, resp->rule_identifier, sizeof(log_entry.rule_identifier) - 1);
            strncpy(log_entry.error_message, resp->error_message, sizeof(log_entry.error_message) - 1);
            log_control_action(&log_entry);

            // Record state
            control_state_entry_t state_entry = {0};
            strncpy(state_entry.device_id, req->device_id, sizeof(state_entry.device_id) - 1);
            strncpy(state_entry.flow_id, req->flow_id, sizeof(state_entry.flow_id) - 1);
            strncpy(state_entry.interface, iface, sizeof(state_entry.interface) - 1);
            snprintf(state_entry.priority, sizeof(state_entry.priority), "%s", target_class);
            strncpy(state_entry.traffic_class, req->traffic_class, sizeof(state_entry.traffic_class) - 1);
            strncpy(state_entry.control_class, target_class, sizeof(state_entry.control_class) - 1);
            strncpy(state_entry.action, "APPLY", sizeof(state_entry.action) - 1);
            strncpy(state_entry.status, resp->status_str, sizeof(state_entry.status) - 1);
            strncpy(state_entry.rule_identifier, resp->rule_identifier, sizeof(state_entry.rule_identifier) - 1);
            state_entry.dry_run = req->dry_run;
            strncpy(state_entry.error_message, resp->error_message, sizeof(state_entry.error_message) - 1);
            record_control_state(&state_entry);

            pthread_mutex_unlock(&interface_mutex);
            return ok;
        }
    } else if (req->command == CMD_REMOVE) {
        if (existing_idx < 0) {
            resp->status = CTRL_STATUS_SKIPPED;
            strncpy(resp->status_str, "SKIPPED", sizeof(resp->status_str) - 1);
            snprintf(resp->error_message, sizeof(resp->error_message), "Flow rule not found for removal");
            pthread_mutex_unlock(&interface_mutex);
            return true;
        }
        uint32_t handle = rule_table[existing_idx].filter_handle;
        bool ok = tc_remove_filter(iface, handle, req->dry_run, &tc_res);
        rule_table[existing_idx].active = false;

        resp->status = req->dry_run ? CTRL_STATUS_DRY_RUN : (ok ? CTRL_STATUS_SUCCESS : CTRL_STATUS_FAILED);
        strncpy(resp->status_str, control_status_to_string(resp->status), sizeof(resp->status_str) - 1);
        strncpy(resp->rule_identifier, tc_res.rule_identifier, sizeof(resp->rule_identifier) - 1);
        strncpy(resp->executed_command, tc_res.generated_command, sizeof(resp->executed_command) - 1);

        control_log_entry_t log_entry = {0};
        strncpy(log_entry.device_id, req->device_id, sizeof(log_entry.device_id) - 1);
        strncpy(log_entry.flow_id, req->flow_id, sizeof(log_entry.flow_id) - 1);
        strncpy(log_entry.action, "REMOVE", sizeof(log_entry.action) - 1);
        strncpy(log_entry.interface, iface, sizeof(log_entry.interface) - 1);
        log_entry.dry_run = req->dry_run;
        strncpy(log_entry.status, resp->status_str, sizeof(log_entry.status) - 1);
        strncpy(log_entry.rule_identifier, resp->rule_identifier, sizeof(log_entry.rule_identifier) - 1);
        log_control_action(&log_entry);

        pthread_mutex_unlock(&interface_mutex);
        return ok;
    } else if (req->command == CMD_STATUS) {
        resp->status = CTRL_STATUS_SUCCESS;
        strncpy(resp->status_str, "SUCCESS", sizeof(resp->status_str) - 1);
        snprintf(resp->executed_command, sizeof(resp->executed_command), "active_rules=%zu", rule_count);
        pthread_mutex_unlock(&interface_mutex);
        return true;
    }

    pthread_mutex_unlock(&interface_mutex);
    return false;
}
