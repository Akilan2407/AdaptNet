#include "control_logger.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <sys/stat.h>

static pthread_mutex_t log_mutex = PTHREAD_MUTEX_INITIALIZER;
static char actions_path[256] = DEFAULT_CONTROL_ACTIONS_CSV;
static char state_path[256]   = DEFAULT_CONTROL_STATE_CSV;
static bool logger_initialized = false;

static void ensure_directory_exists(const char *file_path) {
    char dir_buf[256];
    strncpy(dir_buf, file_path, sizeof(dir_buf) - 1);
    dir_buf[sizeof(dir_buf) - 1] = '\0';
    char *last_slash = strrchr(dir_buf, '/');
    if (last_slash) {
        *last_slash = '\0';
        mkdir(dir_buf, 0755);
    }
}

void get_current_iso_timestamp(char *out_buf, size_t max_len) {
    if (!out_buf || max_len == 0) return;
    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    strftime(out_buf, max_len, "%Y-%m-%d %H:%M:%S", tm_info);
}

bool init_control_logger(const char *act_path, const char *st_path) {
    pthread_mutex_lock(&log_mutex);
    if (act_path && strlen(act_path) > 0) {
        strncpy(actions_path, act_path, sizeof(actions_path) - 1);
    }
    if (st_path && strlen(st_path) > 0) {
        strncpy(state_path, st_path, sizeof(state_path) - 1);
    }

    ensure_directory_exists(actions_path);
    ensure_directory_exists(state_path);

    // Initialize actions CSV with header if new
    FILE *f_act = fopen(actions_path, "r");
    if (!f_act) {
        f_act = fopen(actions_path, "w");
        if (f_act) {
            fprintf(f_act, "timestamp,device_id,flow_id,src_ip,dst_ip,src_port,dst_port,"
                           "protocol,traffic_class,predicted_congestion_class,final_priority,"
                           "action,target_class,interface,dry_run,status,rule_identifier,error_message\n");
            fclose(f_act);
        }
    } else {
        fclose(f_act);
    }

    // Initialize state CSV with header if new
    FILE *f_st = fopen(state_path, "r");
    if (!f_st) {
        f_st = fopen(state_path, "w");
        if (f_st) {
            fprintf(f_st, "timestamp,device_id,flow_id,interface,priority,traffic_class,"
                          "control_class,action,status,rule_identifier,dry_run,error_message\n");
            fclose(f_st);
        }
    } else {
        fclose(f_st);
    }

    logger_initialized = true;
    pthread_mutex_unlock(&log_mutex);
    return true;
}

void close_control_logger(void) {
    pthread_mutex_lock(&log_mutex);
    logger_initialized = false;
    pthread_mutex_unlock(&log_mutex);
}

bool log_control_action(const control_log_entry_t *entry) {
    if (!entry) return false;
    pthread_mutex_lock(&log_mutex);
    if (!logger_initialized) {
        init_control_logger(actions_path, state_path);
    }

    FILE *f = fopen(actions_path, "a");
    if (!f) {
        pthread_mutex_unlock(&log_mutex);
        return false;
    }

    char ts[64];
    if (entry->timestamp[0] != '\0') {
        strncpy(ts, entry->timestamp, sizeof(ts) - 1);
        ts[sizeof(ts) - 1] = '\0';
    } else {
        get_current_iso_timestamp(ts, sizeof(ts));
    }

    fprintf(f, "%s,%s,%s,%s,%s,%u,%u,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n",
        ts,
        entry->device_id,
        entry->flow_id,
        entry->src_ip,
        entry->dst_ip,
        entry->src_port,
        entry->dst_port,
        entry->protocol,
        entry->traffic_class,
        entry->predicted_congestion_class,
        entry->final_priority,
        entry->action,
        entry->target_class,
        entry->interface,
        entry->dry_run ? "true" : "false",
        entry->status,
        entry->rule_identifier,
        entry->error_message
    );

    fflush(f);
    fclose(f);
    pthread_mutex_unlock(&log_mutex);
    return true;
}

bool record_control_state(const control_state_entry_t *entry) {
    if (!entry) return false;
    pthread_mutex_lock(&log_mutex);
    if (!logger_initialized) {
        init_control_logger(actions_path, state_path);
    }

    FILE *f = fopen(state_path, "a");
    if (!f) {
        pthread_mutex_unlock(&log_mutex);
        return false;
    }

    char ts[64];
    if (entry->timestamp[0] != '\0') {
        strncpy(ts, entry->timestamp, sizeof(ts) - 1);
        ts[sizeof(ts) - 1] = '\0';
    } else {
        get_current_iso_timestamp(ts, sizeof(ts));
    }

    fprintf(f, "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n",
        ts,
        entry->device_id,
        entry->flow_id,
        entry->interface,
        entry->priority,
        entry->traffic_class,
        entry->control_class,
        entry->action,
        entry->status,
        entry->rule_identifier,
        entry->dry_run ? "true" : "false",
        entry->error_message
    );

    fflush(f);
    fclose(f);
    pthread_mutex_unlock(&log_mutex);
    return true;
}
