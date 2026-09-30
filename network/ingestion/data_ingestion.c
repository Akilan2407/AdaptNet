#include "data_ingestion.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static data_store_t g_store;
static int g_ingestion_initialized = 0;

int data_ingestion_init(
    size_t buffer_size,
    const char *csv_path,
    const char *jsonl_path,
    const char *invalid_log_path
) {
    if (g_ingestion_initialized) {
        data_ingestion_destroy();
    }

    if (data_store_init(&g_store, buffer_size, csv_path, jsonl_path, invalid_log_path) != 0) {
        return -1;
    }

    g_ingestion_initialized = 1;
    return 0;
}

int data_ingestion_process_raw_line(const char *raw_line, const char *client_addr) {
    if (!g_ingestion_initialized) {
        data_ingestion_init(DEFAULT_BUFFER_CAPACITY, NULL, NULL, NULL);
    }

    pthread_mutex_lock(&g_store.mutex);
    g_store.stats.total_received++;
    pthread_mutex_unlock(&g_store.mutex);

    NetworkRecord record;
    char error_msg[256];
    memset(error_msg, 0, sizeof(error_msg));

    /* 1. Parse raw record */
    if (parse_network_record(raw_line, &record, error_msg, sizeof(error_msg)) != 0) {
        fprintf(stderr, "[!] Ingestion parse error from %s: %s | Raw: '%s'\n",
            client_addr ? client_addr : "local", error_msg, raw_line ? raw_line : "");
        data_store_log_invalid(&g_store, raw_line, error_msg);
        return -1;
    }

    /* 2. Validate record fields and network ranges */
    if (!validate_network_record(&record, error_msg, sizeof(error_msg))) {
        fprintf(stderr, "[!] Ingestion validation error from %s: %s | Raw: '%s'\n",
            client_addr ? client_addr : "local", error_msg, raw_line ? raw_line : "");
        data_store_log_invalid(&g_store, raw_line, error_msg);
        return -1;
    }

    /* 3. Insert into data store (duplicate check + ring buffer + storage + device tracker) */
    int insert_res = data_store_insert_record(&g_store, &record);
    if (insert_res == 1) {
        /* Duplicate record */
        printf("  [i] Duplicate record ignored from %s [%s: %s -> %s]\n",
            client_addr ? client_addr : "local", record.device_id, record.src_ip, record.dst_ip);
        return 1;
    }

    return 0;
}

void data_ingestion_print_stats(void) {
    if (!g_ingestion_initialized) return;

    ingestion_stats_t stats;
    data_store_get_stats(&g_store, &stats);

    printf("\n========================================\n");
    printf("NETWORK DATA INGESTION\n");
    printf("========================================\n");
    printf("Records received : %llu\n", (unsigned long long)stats.total_received);
    printf("Valid records    : %llu\n", (unsigned long long)stats.valid_records);
    printf("Invalid records  : %llu\n", (unsigned long long)stats.invalid_records);
    printf("Duplicates       : %llu\n", (unsigned long long)stats.duplicate_records);
    printf("TCP records      : %llu\n", (unsigned long long)stats.tcp_records);
    printf("UDP records      : %llu\n", (unsigned long long)stats.udp_records);
    printf("Devices tracked  : %zu\n", stats.devices_tracked);
    printf("Buffer size      : %zu (Current: %zu)\n", stats.buffer_capacity, stats.buffer_count);
    printf("========================================\n\n");
}

void data_ingestion_get_stats(ingestion_stats_t *out_stats) {
    if (!out_stats) return;
    if (!g_ingestion_initialized) {
        memset(out_stats, 0, sizeof(ingestion_stats_t));
        return;
    }
    data_store_get_stats(&g_store, out_stats);
}

void data_ingestion_destroy(void) {
    if (g_ingestion_initialized) {
        data_store_destroy(&g_store);
        g_ingestion_initialized = 0;
    }
}
