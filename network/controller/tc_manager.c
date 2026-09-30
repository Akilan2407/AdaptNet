#include "tc_manager.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

const char* priority_to_tc_class(priority_level_t prio) {
    switch (prio) {
        case PRIO_LEVEL_HIGH:   return HTB_CLASS_HIGH;
        case PRIO_LEVEL_MEDIUM: return HTB_CLASS_MEDIUM;
        case PRIO_LEVEL_NORMAL: return HTB_CLASS_NORMAL;
        case PRIO_LEVEL_LOW:    return HTB_CLASS_LOW;
        default:                return HTB_CLASS_NORMAL;
    }
}

priority_level_t parse_priority_string(const char *str) {
    if (!str) return PRIO_LEVEL_UNKNOWN;
    if (strcasecmp(str, "HIGH") == 0)   return PRIO_LEVEL_HIGH;
    if (strcasecmp(str, "MEDIUM") == 0) return PRIO_LEVEL_MEDIUM;
    if (strcasecmp(str, "NORMAL") == 0) return PRIO_LEVEL_NORMAL;
    if (strcasecmp(str, "LOW") == 0)    return PRIO_LEVEL_LOW;
    return PRIO_LEVEL_UNKNOWN;
}

static int execute_or_simulate_cmd(const char *cmd, bool dry_run, char *err_buf, size_t err_len) {
    if (dry_run) {
        if (err_buf && err_len > 0) err_buf[0] = '\0';
        return 0;
    }

#ifdef __linux__
    int ret = system(cmd);
    if (ret != 0) {
        if (err_buf && err_len > 0) {
            snprintf(err_buf, err_len, "Command exited with status %d", ret);
        }
        return ret;
    }
    return 0;
#else
    // On macOS / non-Linux host, actual tc is unavailable
    (void)cmd;
    if (err_buf && err_len > 0) {
        snprintf(err_buf, err_len, "tc is Linux-only; simulated execution on Darwin");
    }
    return 0;
#endif
}

bool tc_init_interface(const char *interface, bool dry_run, tc_operation_result_t *result) {
    if (!result) return false;
    memset(result, 0, sizeof(tc_operation_result_t));
    strncpy(result->interface, interface ? interface : "unknown", sizeof(result->interface) - 1);

    if (!is_allowlisted_interface(interface)) {
        snprintf(result->error_message, sizeof(result->error_message),
                 "Interface '%s' not in allowlist", interface ? interface : "(null)");
        result->status_code = -1;
        return false;
    }

    // Build multi-step batch command for root qdisc + HTB class hierarchy
    char batch_cmd[MAX_CMD_LEN];
    snprintf(batch_cmd, sizeof(batch_cmd),
        "tc qdisc add dev %s root handle 1: htb default %d && "
        "tc class add dev %s parent 1: classid 1:1 htb rate %s ceil %s && "
        "tc class add dev %s parent 1:1 classid 1:10 htb rate %s ceil %s prio %d && "
        "tc class add dev %s parent 1:1 classid 1:20 htb rate %s ceil %s prio %d && "
        "tc class add dev %s parent 1:1 classid 1:30 htb rate %s ceil %s prio %d && "
        "tc class add dev %s parent 1:1 classid 1:40 htb rate %s ceil %s prio %d",
        interface, HTB_DEFAULT_CLASS_NUM,
        interface, RATE_ROOT_TOTAL, RATE_ROOT_TOTAL,
        interface, RATE_HIGH, CEIL_HIGH, TC_PRIO_HIGH,
        interface, RATE_MEDIUM, CEIL_MEDIUM, TC_PRIO_MEDIUM,
        interface, RATE_NORMAL, CEIL_NORMAL, TC_PRIO_NORMAL,
        interface, RATE_LOW, CEIL_LOW, TC_PRIO_LOW
    );

    strncpy(result->generated_command, batch_cmd, sizeof(result->generated_command) - 1);
    snprintf(result->rule_identifier, sizeof(result->rule_identifier), "%s_htb_root", interface);
    result->executed = !dry_run;

    int ret = execute_or_simulate_cmd(batch_cmd, dry_run, result->error_message, sizeof(result->error_message));
    result->status_code = ret;
    return (ret == 0);
}

bool tc_reset_interface(const char *interface, bool dry_run, tc_operation_result_t *result) {
    if (!result) return false;
    memset(result, 0, sizeof(tc_operation_result_t));
    strncpy(result->interface, interface ? interface : "unknown", sizeof(result->interface) - 1);

    if (!is_allowlisted_interface(interface)) {
        snprintf(result->error_message, sizeof(result->error_message),
                 "Interface '%s' not in allowlist", interface ? interface : "(null)");
        result->status_code = -1;
        return false;
    }

    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd), "tc qdisc del dev %s root handle 1:", interface);
    strncpy(result->generated_command, cmd, sizeof(result->generated_command) - 1);
    snprintf(result->rule_identifier, sizeof(result->rule_identifier), "%s_reset", interface);
    result->executed = !dry_run;

    int ret = execute_or_simulate_cmd(cmd, dry_run, result->error_message, sizeof(result->error_message));
    result->status_code = ret;
    return (ret == 0);
}

bool tc_apply_filter(
    const char *interface,
    const flow_tuple_t *flow,
    const char *target_class,
    uint32_t filter_handle,
    bool dry_run,
    tc_operation_result_t *result
) {
    if (!result) return false;
    memset(result, 0, sizeof(tc_operation_result_t));
    strncpy(result->interface, interface ? interface : "unknown", sizeof(result->interface) - 1);
    strncpy(result->target_class, target_class ? target_class : HTB_CLASS_NORMAL, sizeof(result->target_class) - 1);

    if (!is_allowlisted_interface(interface)) {
        snprintf(result->error_message, sizeof(result->error_message),
                 "Interface '%s' not allowlisted", interface ? interface : "(null)");
        result->status_code = -1;
        return false;
    }
    if (!flow || !is_valid_ipv4(flow->src_ip) || !is_valid_port(flow->dst_port)) {
        snprintf(result->error_message, sizeof(result->error_message), "Invalid flow parameters");
        result->status_code = -1;
        return false;
    }

    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd),
        "tc filter add dev %s protocol ip parent 1:0 prio 1 handle 0x%x u32 match ip src %s/32 match ip dport %d 0xffff flowid %s",
        interface, filter_handle, flow->src_ip, flow->dst_port, result->target_class
    );

    strncpy(result->generated_command, cmd, sizeof(result->generated_command) - 1);
    snprintf(result->rule_identifier, sizeof(result->rule_identifier), "%s_0x%x_%s",
             interface, filter_handle, result->target_class);
    result->executed = !dry_run;

    int ret = execute_or_simulate_cmd(cmd, dry_run, result->error_message, sizeof(result->error_message));
    result->status_code = ret;
    return (ret == 0);
}

bool tc_update_filter(
    const char *interface,
    const flow_tuple_t *flow,
    const char *new_target_class,
    uint32_t filter_handle,
    bool dry_run,
    tc_operation_result_t *result
) {
    if (!result) return false;
    memset(result, 0, sizeof(tc_operation_result_t));
    strncpy(result->interface, interface ? interface : "unknown", sizeof(result->interface) - 1);
    strncpy(result->target_class, new_target_class ? new_target_class : HTB_CLASS_NORMAL, sizeof(result->target_class) - 1);

    if (!is_allowlisted_interface(interface)) {
        snprintf(result->error_message, sizeof(result->error_message),
                 "Interface '%s' not allowlisted", interface ? interface : "(null)");
        result->status_code = -1;
        return false;
    }

    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd),
        "tc filter change dev %s protocol ip parent 1:0 prio 1 handle 0x%x u32 match ip src %s/32 match ip dport %d 0xffff flowid %s",
        interface, filter_handle, flow->src_ip, flow->dst_port, result->target_class
    );

    strncpy(result->generated_command, cmd, sizeof(result->generated_command) - 1);
    snprintf(result->rule_identifier, sizeof(result->rule_identifier), "%s_0x%x_%s",
             interface, filter_handle, result->target_class);
    result->executed = !dry_run;

    int ret = execute_or_simulate_cmd(cmd, dry_run, result->error_message, sizeof(result->error_message));
    result->status_code = ret;
    return (ret == 0);
}

bool tc_remove_filter(
    const char *interface,
    uint32_t filter_handle,
    bool dry_run,
    tc_operation_result_t *result
) {
    if (!result) return false;
    memset(result, 0, sizeof(tc_operation_result_t));
    strncpy(result->interface, interface ? interface : "unknown", sizeof(result->interface) - 1);

    if (!is_allowlisted_interface(interface)) {
        snprintf(result->error_message, sizeof(result->error_message),
                 "Interface '%s' not allowlisted", interface ? interface : "(null)");
        result->status_code = -1;
        return false;
    }

    char cmd[MAX_CMD_LEN];
    snprintf(cmd, sizeof(cmd),
        "tc filter del dev %s protocol ip parent 1:0 prio 1 handle 0x%x u32",
        interface, filter_handle
    );

    strncpy(result->generated_command, cmd, sizeof(result->generated_command) - 1);
    snprintf(result->rule_identifier, sizeof(result->rule_identifier), "%s_0x%x_del",
             interface, filter_handle);
    result->executed = !dry_run;

    int ret = execute_or_simulate_cmd(cmd, dry_run, result->error_message, sizeof(result->error_message));
    result->status_code = ret;
    return (ret == 0);
}
