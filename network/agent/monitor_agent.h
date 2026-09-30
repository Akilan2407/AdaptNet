#ifndef MONITOR_AGENT_H
#define MONITOR_AGENT_H

#include <stdint.h>
#include <stddef.h>

#define DEFAULT_MONITOR_INTERVAL_SEC 1.0
#define DEFAULT_CSV_OUTPUT_PATH "data/monitoring/network_metrics.csv"
#define DEFAULT_DEVICE_ID "h1"

/* Agent Configuration Options */
typedef struct {
    char device_id[64];
    char iface_name[32];
    char output_csv[256];
    char server_ip[64];
    int server_port;
    int enable_socket;    /* 1 = stream over TCP socket, 0 = local only */
    double interval_sec;
    double retry_interval_sec;
    int max_samples;      /* 0 = continuous until SIGINT */
    int verbose;
} agent_config_t;

/* Parse CLI arguments into agent_config_t */
int parse_agent_args(int argc, char *argv[], agent_config_t *config);

/* Run main monitoring loop */
int run_monitoring_agent(const agent_config_t *config);

#endif /* MONITOR_AGENT_H */
