#include "data_store.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>

static void ensure_parent_dir(const char *filepath) {
    if (!filepath) return;
    char dirpath[512];
    snprintf(dirpath, sizeof(dirpath), "%s", filepath);
    char *last_slash = strrchr(dirpath, '/');
    if (last_slash) {
        *last_slash = '\0';
        char cmd[600];
        snprintf(cmd, sizeof(cmd), "mkdir -p '%s' 2>/dev/null", dirpath);
        int ret = system(cmd);
        (void)ret;
    }
}

int data_store_init(
    data_store_t *store,
    size_t buffer_capacity,
    const char *csv_path,
    const char *jsonl_path,
    const char *invalid_log_path
) {
    if (!store) return -1;
    memset(store, 0, sizeof(data_store_t));

    store->buffer_capacity = (buffer_capacity > 0) ? buffer_capacity : DEFAULT_BUFFER_CAPACITY;
    store->ring_buffer = (NetworkRecord *)calloc(store->buffer_capacity, sizeof(NetworkRecord));
    if (!store->ring_buffer) {
        fprintf(stderr, "[!] Failed to allocate ring buffer memory\n");
        return -1;
    }
    store->buffer_head = 0;
    store->buffer_count = 0;

    snprintf(store->csv_path, sizeof(store->csv_path), "%s", csv_path ? csv_path : DEFAULT_METRICS_CSV_PATH);
    snprintf(store->jsonl_path, sizeof(store->jsonl_path), "%s", jsonl_path ? jsonl_path : DEFAULT_METRICS_JSONL_PATH);
    snprintf(store->invalid_log_path, sizeof(store->invalid_log_path), "%s", invalid_log_path ? invalid_log_path : DEFAULT_INVALID_LOG_PATH);

    ensure_parent_dir(store->csv_path);
    ensure_parent_dir(store->jsonl_path);
    ensure_parent_dir(store->invalid_log_path);

    /* Open CSV (write header if new) */
    int write_csv_header = (access(store->csv_path, F_OK) != 0);
    store->csv_fp = fopen(store->csv_path, "a");
    if (store->csv_fp && write_csv_header) {
        fprintf(store->csv_fp, "timestamp,device_id,src_ip,dst_ip,src_port,dst_port,protocol,throughput,rtt,packet_loss,active_connections\n");
        fflush(store->csv_fp);
    }

    /* Open JSONL */
    store->jsonl_fp = fopen(store->jsonl_path, "a");

    /* Open Invalid Log */
    store->invalid_fp = fopen(store->invalid_log_path, "a");

    pthread_mutex_init(&store->mutex, NULL);
    return 0;
}

int data_store_is_duplicate(data_store_t *store, const NetworkRecord *record) {
    if (!store || !record || store->buffer_count == 0) return 0;

    /* Search backwards in recent buffer (up to 200 recent records for efficiency) */
    size_t scan_limit = (store->buffer_count < 200) ? store->buffer_count : 200;
    size_t idx = (store->buffer_head == 0) ? (store->buffer_capacity - 1) : (store->buffer_head - 1);

    for (size_t i = 0; i < scan_limit; i++) {
        const NetworkRecord *existing = &store->ring_buffer[idx];
        if (strcmp(existing->measurement_timestamp, record->measurement_timestamp) == 0 &&
            strcmp(existing->device_id, record->device_id) == 0 &&
            strcmp(existing->src_ip, record->src_ip) == 0 &&
            strcmp(existing->dst_ip, record->dst_ip) == 0 &&
            existing->src_port == record->src_port &&
            existing->dst_port == record->dst_port &&
            strcmp(existing->protocol, record->protocol) == 0) {
            return 1; /* Duplicate match */
        }
        idx = (idx == 0) ? (store->buffer_capacity - 1) : (idx - 1);
    }
    return 0;
}

static void update_device_tracker(data_store_t *store, const NetworkRecord *record) {
    device_tracker_t *target = NULL;

    for (size_t i = 0; i < store->device_count; i++) {
        if (strcmp(store->devices[i].device_id, record->device_id) == 0) {
            target = &store->devices[i];
            break;
        }
    }

    if (!target && store->device_count < MAX_TRACKED_DEVICES) {
        target = &store->devices[store->device_count++];
        memset(target, 0, sizeof(device_tracker_t));
        snprintf(target->device_id, sizeof(target->device_id), "%s", record->device_id);
    }

    if (target) {
        target->total_records++;
        if (strcmp(record->protocol, "TCP") == 0) target->tcp_records++;
        else if (strcmp(record->protocol, "UDP") == 0) target->udp_records++;

        snprintf(target->last_timestamp, sizeof(target->last_timestamp), "%s", record->measurement_timestamp);
        snprintf(target->last_protocol, sizeof(target->last_protocol), "%s", record->protocol);
        target->last_throughput = record->throughput_mbps;
    }
}

int data_store_insert_record(data_store_t *store, const NetworkRecord *record) {
    if (!store || !record) return -1;

    pthread_mutex_lock(&store->mutex);

    /* 1. Duplicate check */
    if (data_store_is_duplicate(store, record)) {
        store->stats.duplicate_records++;
        pthread_mutex_unlock(&store->mutex);
        data_store_log_invalid(store, "DUPLICATE", "Duplicate record detected (already in recent buffer)");
        return 1; /* Duplicate detected */
    }

    /* 2. Insert into Ring Buffer */
    store->ring_buffer[store->buffer_head] = *record;
    store->buffer_head = (store->buffer_head + 1) % store->buffer_capacity;
    if (store->buffer_count < store->buffer_capacity) {
        store->buffer_count++;
    }

    /* 3. Update Device Tracking */
    update_device_tracker(store, record);

    /* 4. Update Statistics */
    store->stats.valid_records++;
    if (strcmp(record->protocol, "TCP") == 0) store->stats.tcp_records++;
    else if (strcmp(record->protocol, "UDP") == 0) store->stats.udp_records++;

    /* 5. Write to CSV */
    if (store->csv_fp) {
        char rtt_str[32], loss_str[32];
        if (record->has_rtt) snprintf(rtt_str, sizeof(rtt_str), "%.2f", record->rtt_ms);
        else snprintf(rtt_str, sizeof(rtt_str), "N/A");

        if (record->has_packet_loss) snprintf(loss_str, sizeof(loss_str), "%.2f", record->packet_loss_pct);
        else snprintf(loss_str, sizeof(loss_str), "N/A");

        fprintf(store->csv_fp, "%s,%s,%s,%s,%d,%d,%s,%.2f,%s,%s,%d\n",
            record->measurement_timestamp,
            record->device_id,
            record->src_ip,
            record->dst_ip,
            record->src_port,
            record->dst_port,
            record->protocol,
            record->throughput_mbps,
            rtt_str,
            loss_str,
            record->active_connections
        );
        fflush(store->csv_fp);
    }

    /* 6. Write to JSONL */
    if (store->jsonl_fp) {
        char rtt_json[32];
        char loss_json[32];
        if (record->has_rtt) snprintf(rtt_json, sizeof(rtt_json), "%.2f", record->rtt_ms);
        else snprintf(rtt_json, sizeof(rtt_json), "null");

        if (record->has_packet_loss) snprintf(loss_json, sizeof(loss_json), "%.2f", record->packet_loss_pct);
        else snprintf(loss_json, sizeof(loss_json), "null");

        fprintf(store->jsonl_fp,
            "{\"timestamp\":\"%s\",\"ingestion_timestamp\":\"%s\",\"device_id\":\"%s\",\"src_ip\":\"%s\",\"dst_ip\":\"%s\","
            "\"src_port\":%d,\"dst_port\":%d,\"protocol\":\"%s\",\"throughput\":%.2f,"
            "\"rtt\":%s,\"packet_loss\":%s,\"active_connections\":%d}\n",
            record->measurement_timestamp,
            record->ingestion_timestamp,
            record->device_id,
            record->src_ip,
            record->dst_ip,
            record->src_port,
            record->dst_port,
            record->protocol,
            record->throughput_mbps,
            rtt_json,
            loss_json,
            record->active_connections
        );
        fflush(store->jsonl_fp);
    }

    pthread_mutex_unlock(&store->mutex);
    return 0;
}

int data_store_log_invalid(data_store_t *store, const char *raw_line, const char *reason) {
    if (!store) return -1;

    pthread_mutex_lock(&store->mutex);
    store->stats.invalid_records++;

    if (store->invalid_fp) {
        char ts[MAX_TIMESTAMP_STR];
        get_current_ingestion_timestamp(ts, sizeof(ts));
        fprintf(store->invalid_fp, "[%s] REJECTED (%s): %s\n", ts, reason ? reason : "Unknown error", raw_line ? raw_line : "");
        fflush(store->invalid_fp);
    }

    pthread_mutex_unlock(&store->mutex);
    return 0;
}

void data_store_get_stats(data_store_t *store, ingestion_stats_t *out_stats) {
    if (!store || !out_stats) return;
    pthread_mutex_lock(&store->mutex);
    *out_stats = store->stats;
    out_stats->devices_tracked = store->device_count;
    out_stats->buffer_count = store->buffer_count;
    out_stats->buffer_capacity = store->buffer_capacity;
    pthread_mutex_unlock(&store->mutex);
}

size_t data_store_get_recent_records(data_store_t *store, NetworkRecord *out_array, size_t max_records) {
    if (!store || !out_array || max_records == 0) return 0;

    pthread_mutex_lock(&store->mutex);
    size_t to_copy = (store->buffer_count < max_records) ? store->buffer_count : max_records;

    /* Copy in reverse chronological order (newest first) */
    size_t idx = (store->buffer_head == 0) ? (store->buffer_capacity - 1) : (store->buffer_head - 1);
    for (size_t i = 0; i < to_copy; i++) {
        out_array[i] = store->ring_buffer[idx];
        idx = (idx == 0) ? (store->buffer_capacity - 1) : (idx - 1);
    }

    pthread_mutex_unlock(&store->mutex);
    return to_copy;
}

void data_store_destroy(data_store_t *store) {
    if (!store) return;
    pthread_mutex_lock(&store->mutex);

    if (store->ring_buffer) {
        free(store->ring_buffer);
        store->ring_buffer = NULL;
    }
    if (store->csv_fp) {
        fclose(store->csv_fp);
        store->csv_fp = NULL;
    }
    if (store->jsonl_fp) {
        fclose(store->jsonl_fp);
        store->jsonl_fp = NULL;
    }
    if (store->invalid_fp) {
        fclose(store->invalid_fp);
        store->invalid_fp = NULL;
    }

    pthread_mutex_unlock(&store->mutex);
    pthread_mutex_destroy(&store->mutex);
}
