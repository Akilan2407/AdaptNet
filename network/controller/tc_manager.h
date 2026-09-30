#ifndef TC_MANAGER_H
#define TC_MANAGER_H

#include <stdbool.h>
#include <stdint.h>
#include "control_config.h"
#include "flow_mapper.h"

typedef struct {
    char rule_identifier[MAX_RULE_ID_LEN];
    char interface[MAX_IFACE_LEN];
    char target_class[16];
    char generated_command[MAX_CMD_LEN];
    int status_code;
    char error_message[MAX_ERR_MSG_LEN];
    bool executed;
} tc_operation_result_t;

/* TC Subsystem Initialization & Teardown */
bool tc_init_interface(const char *interface, bool dry_run, tc_operation_result_t *result);
bool tc_reset_interface(const char *interface, bool dry_run, tc_operation_result_t *result);

/* Filter Manipulation */
bool tc_apply_filter(
    const char *interface,
    const flow_tuple_t *flow,
    const char *target_class,
    uint32_t filter_handle,
    bool dry_run,
    tc_operation_result_t *result
);

bool tc_update_filter(
    const char *interface,
    const flow_tuple_t *flow,
    const char *new_target_class,
    uint32_t filter_handle,
    bool dry_run,
    tc_operation_result_t *result
);

bool tc_remove_filter(
    const char *interface,
    uint32_t filter_handle,
    bool dry_run,
    tc_operation_result_t *result
);

/* Helper mapping priority string / enum to target class */
const char* priority_to_tc_class(priority_level_t prio);
priority_level_t parse_priority_string(const char *str);

#endif /* TC_MANAGER_H */
