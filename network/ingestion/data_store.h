#ifndef DATA_STORE_H
#define DATA_STORE_H

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <pthread.h>
#include "record_parser.h"

#define DEFAULT_BUFFER_CAPACITY 1000
#define MAX_TRACKED_DEVICES 64
#define DEFAULT_METRICS_CSV_PATH "data/monitoring/network_metrics.csv"
#define DEFAULT_METRICS_JSONL_PATH "data/monitoring/network_metrics.jsonl"
#define DEFAULT_INVALID_LOG_PATH "data/monitoring/invalid_records.log"

typedef struct {
    char device_id[MAX_DEVICE_NAME];
    uint64_t total_records;
    uint64_t tcp_records;
    uint64_t udp_records;
    char last_timestamp[MAX_TIMESTAMP_STR];
    char last_protocol[MAX_PROTO_STR];
    double last_throughput;
} device_tracker_t;

typedef struct {
    uint64_t total_received;
    uint64_t valid_records;
    uint64_t invalid_records;
    uint64_t duplicate_records;
    uint64_t tcp_records;
    uint64_t udp_records;
    size_t devices_tracked;
    size_t buffer_count;
    size_t buffer_capacity;
} ingestion_stats_t;

typedef struct {
    /* Ring Buffer */
    NetworkRecord *ring_buffer;
    size_t buffer_capacity;
    size_t buffer_head;
    size_t buffer_count;

    /* Device Tracking */
    device_tracker_t devices[MAX_TRACKED_DEVICES];
    size_t device_count;

    /* Counters */
    ingestion_stats_t stats;

    /* Files */
    char csv_path[256];
    char jsonl_path[256];
    char invalid_log_path[256];
    FILE *csv_fp;
    FILE *jsonl_fp;
    FILE *invalid_fp;

    /* Synchronization */
    pthread_mutex_t mutex;
} data_store_t;

/* Initialize data store with configurable ring buffer capacity and output paths */
int data_store_init(data_store_t *store, size_t buffer_capacity, const char *csv_path, const char *jsonl_path, const char *invalid_log_path);

/* Check if a record is an exact duplicate of a recent record in the buffer */
int data_store_is_duplicate(data_store_t *store, const NetworkRecord *record);

/* Store a validated NetworkRecord (ring buffer + CSV + JSONL + device tracker) */
int data_store_insert_record(data_store_t *store, const NetworkRecord *record);

/* Log an invalid or rejected raw line with rejection reason */
int data_store_log_invalid(data_store_t *store, const char *raw_line, const char *reason);

/* Get snapshot of current ingestion statistics */
void data_store_get_stats(data_store_t *store, ingestion_stats_t *out_stats);

/* Retrieve records from recent ring buffer (up to max_records) */
size_t data_store_get_recent_records(data_store_t *store, NetworkRecord *out_array, size_t max_records);

/* Close all open file descriptors and free memory */
void data_store_destroy(data_store_t *store);

#endif /* DATA_STORE_H */
