#ifndef NETWORK_CONTROLLER_H
#define NETWORK_CONTROLLER_H

#include <stddef.h>
#include <stdint.h>
#include <pthread.h>

#define DEFAULT_CONTROLLER_BIND_IP "0.0.0.0"
#define DEFAULT_CONTROLLER_LISTEN_PORT 5000
#define DEFAULT_METRICS_CSV "data/monitoring/network_metrics.csv"
#define DEFAULT_METRICS_JSONL "data/monitoring/network_metrics.jsonl"
#define DEFAULT_INVALID_LOG "data/monitoring/invalid_records.log"
#define MAX_PENDING_CONNECTIONS 128

typedef struct {
    char bind_ip[64];
    int port;
    char output_csv[256];
    char output_jsonl[256];
    char invalid_log[256];
    size_t buffer_size;
    int verbose;
} controller_config_t;

int parse_controller_args(int argc, char *argv[], controller_config_t *config);
int run_network_controller(const controller_config_t *config);

#endif /* NETWORK_CONTROLLER_H */
