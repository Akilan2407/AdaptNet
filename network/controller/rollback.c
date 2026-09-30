#include "rollback.h"
#include "tc_manager.h"
#include "control_logger.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>

static char managed_ifaces[MAX_MANAGED_INTERFACES][MAX_IFACE_LEN];
static size_t managed_count = 0;
static pthread_mutex_t rollback_mutex = PTHREAD_MUTEX_INITIALIZER;

bool register_managed_interface(const char *interface) {
    if (!interface || strlen(interface) == 0) return false;
    pthread_mutex_lock(&rollback_mutex);
    for (size_t i = 0; i < managed_count; i++) {
        if (strcmp(managed_ifaces[i], interface) == 0) {
            pthread_mutex_unlock(&rollback_mutex);
            return true; // Already registered
        }
    }
    if (managed_count < MAX_MANAGED_INTERFACES) {
        strncpy(managed_ifaces[managed_count], interface, MAX_IFACE_LEN - 1);
        managed_ifaces[managed_count][MAX_IFACE_LEN - 1] = '\0';
        managed_count++;
        pthread_mutex_unlock(&rollback_mutex);
        return true;
    }
    pthread_mutex_unlock(&rollback_mutex);
    return false;
}

bool unregister_managed_interface(const char *interface) {
    if (!interface) return false;
    pthread_mutex_lock(&rollback_mutex);
    for (size_t i = 0; i < managed_count; i++) {
        if (strcmp(managed_ifaces[i], interface) == 0) {
            for (size_t j = i; j < managed_count - 1; j++) {
                strncpy(managed_ifaces[j], managed_ifaces[j + 1], MAX_IFACE_LEN);
            }
            managed_count--;
            pthread_mutex_unlock(&rollback_mutex);
            return true;
        }
    }
    pthread_mutex_unlock(&rollback_mutex);
    return false;
}

size_t get_managed_interfaces(char out_interfaces[MAX_MANAGED_INTERFACES][MAX_IFACE_LEN]) {
    pthread_mutex_lock(&rollback_mutex);
    size_t count = managed_count;
    for (size_t i = 0; i < count; i++) {
        strncpy(out_interfaces[i], managed_ifaces[i], MAX_IFACE_LEN);
    }
    pthread_mutex_unlock(&rollback_mutex);
    return count;
}

bool rollback_interface(const char *interface, bool dry_run, char *err_msg, size_t err_len) {
    if (!interface) return false;
    tc_operation_result_t tc_res;
    bool ok = tc_reset_interface(interface, dry_run, &tc_res);

    control_log_entry_t log_entry;
    memset(&log_entry, 0, sizeof(log_entry));
    get_current_iso_timestamp(log_entry.timestamp, sizeof(log_entry.timestamp));
    strncpy(log_entry.action, "RESET", sizeof(log_entry.action) - 1);
    strncpy(log_entry.interface, interface, sizeof(log_entry.interface) - 1);
    log_entry.dry_run = dry_run;
    strncpy(log_entry.status, dry_run ? "DRY_RUN" : (ok ? "SUCCESS" : "FAILED"), sizeof(log_entry.status) - 1);
    strncpy(log_entry.rule_identifier, tc_res.rule_identifier, sizeof(log_entry.rule_identifier) - 1);
    strncpy(log_entry.error_message, tc_res.error_message, sizeof(log_entry.error_message) - 1);

    log_control_action(&log_entry);

    if (!ok && err_msg && err_len > 0) {
        snprintf(err_msg, err_len, "%s", tc_res.error_message);
    }

    if (ok) {
        unregister_managed_interface(interface);
    }
    return ok;
}

int rollback_all(bool dry_run, char *err_msg, size_t err_len) {
    char ifaces[MAX_MANAGED_INTERFACES][MAX_IFACE_LEN];
    size_t count = get_managed_interfaces(ifaces);
    int rolled_back = 0;

    for (size_t i = 0; i < count; i++) {
        if (rollback_interface(ifaces[i], dry_run, err_msg, err_len)) {
            rolled_back++;
        }
    }
    return rolled_back;
}
