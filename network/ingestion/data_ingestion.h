#ifndef DATA_INGESTION_H
#define DATA_INGESTION_H

#include <stddef.h>
#include <stdint.h>
#include "record_parser.h"
#include "data_validator.h"
#include "data_store.h"

/*
 * Initialize the global data ingestion pipeline.
 */
int data_ingestion_init(size_t buffer_size, const char *csv_path, const char *jsonl_path, const char *invalid_log_path);

/*
 * Ingest a single raw stream line received from a monitoring agent.
 * Handles parsing, validation, duplicate checking, ring buffering, and persistence.
 * Returns 0 on success, 1 on duplicate, -1 on parsing/validation error.
 */
int data_ingestion_process_raw_line(const char *raw_line, const char *client_addr);

/* Print current ingestion statistics to stdout */
void data_ingestion_print_stats(void);

/* Retrieve snapshot of ingestion statistics */
void data_ingestion_get_stats(ingestion_stats_t *out_stats);

/* Teardown ingestion pipeline and flush all storage */
void data_ingestion_destroy(void);

#endif /* DATA_INGESTION_H */
