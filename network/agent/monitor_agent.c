#include "monitor_agent.h"
#include "flow_monitor.h"
#include "network_stats.h"
#include "socket_client.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>

static volatile sig_atomic_t g_running = 1;

static void handle_sigint(int sig) {
    (void)sig;
    g_running = 0;
}

static void print_usage(const char *prog_name) {
    printf("Usage: %s [DEVICE_ID] [OPTIONS]\n", prog_name);
    printf("       %s --host <DEVICE_ID> [OPTIONS]\n\n", prog_name);
    printf("Options:\n");
    printf("  --host <id>             Set device/host identifier (e.g., h1, h2, h3)\n");
    printf("  --server <ip>           Central C controller IP address (e.g., 127.0.0.1)\n");
    printf("  --port <port>           Central C controller port (e.g., 5000)\n");
    printf("  --interval <sec>        Sampling interval in seconds (default: 1.0)\n");
    printf("  --retry-interval <sec>  Connection retry delay in seconds (default: 2.0)\n");
    printf("  --output <file>         CSV output destination (default: %s)\n", DEFAULT_CSV_OUTPUT_PATH);
    printf("  --interface <name>      Network interface to monitor (default: first active non-lo)\n");
    printf("  --count <N>             Exit after N samples (default: 0 = continuous until Ctrl+C)\n");
    printf("  --help, -h              Display this help message\n");
}

int parse_agent_args(int argc, char *argv[], agent_config_t *config) {
    if (!config) return -1;

    /* Defaults */
    memset(config, 0, sizeof(agent_config_t));
    snprintf(config->device_id, sizeof(config->device_id), "%s", DEFAULT_DEVICE_ID);
    config->interval_sec = DEFAULT_MONITOR_INTERVAL_SEC;
    config->retry_interval_sec = DEFAULT_RETRY_INTERVAL_SEC;
    snprintf(config->output_csv, sizeof(config->output_csv), "%s", DEFAULT_CSV_OUTPUT_PATH);
    config->server_port = 0;
    config->enable_socket = 0;
    config->max_samples = 0;
    config->verbose = 1;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            print_usage(argv[0]);
            exit(0);
        } else if (strcmp(argv[i], "--host") == 0 && i + 1 < argc) {
            snprintf(config->device_id, sizeof(config->device_id), "%s", argv[++i]);
        } else if (strcmp(argv[i], "--server") == 0 && i + 1 < argc) {
            snprintf(config->server_ip, sizeof(config->server_ip), "%s", argv[++i]);
            config->enable_socket = 1;
            if (config->server_port == 0) {
                config->server_port = DEFAULT_CONTROLLER_PORT;
            }
        } else if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
            config->server_port = atoi(argv[++i]);
            config->enable_socket = 1;
            if (config->server_ip[0] == '\0') {
                snprintf(config->server_ip, sizeof(config->server_ip), "%s", DEFAULT_CONTROLLER_IP);
            }
        } else if (strcmp(argv[i], "--interval") == 0 && i + 1 < argc) {
            config->interval_sec = atof(argv[++i]);
            if (config->interval_sec <= 0.0) {
                fprintf(stderr, "[ERROR] Invalid interval: %s. Must be positive.\n", argv[i]);
                return -1;
            }
        } else if (strcmp(argv[i], "--retry-interval") == 0 && i + 1 < argc) {
            config->retry_interval_sec = atof(argv[++i]);
        } else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc) {
            snprintf(config->output_csv, sizeof(config->output_csv), "%s", argv[++i]);
        } else if (strcmp(argv[i], "--interface") == 0 && i + 1 < argc) {
            snprintf(config->iface_name, sizeof(config->iface_name), "%s", argv[++i]);
        } else if (strcmp(argv[i], "--count") == 0 && i + 1 < argc) {
            config->max_samples = atoi(argv[++i]);
        } else if (argv[i][0] != '-') {
            /* Positional argument for device ID */
            snprintf(config->device_id, sizeof(config->device_id), "%s", argv[i]);
        } else {
            fprintf(stderr, "[ERROR] Unknown option '%s'\n", argv[i]);
            print_usage(argv[0]);
            return -1;
        }
    }
    return 0;
}

static void ensure_parent_dir_exists(const char *filepath) {
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

int run_monitoring_agent(const agent_config_t *config) {
    if (!config) return -1;

    /* Setup signal handler for graceful shutdown */
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = handle_sigint;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    ensure_parent_dir_exists(config->output_csv);

    /* Open CSV file */
    int write_header = (access(config->output_csv, F_OK) != 0);
    FILE *csv_fp = fopen(config->output_csv, "a");
    if (!csv_fp) {
        fprintf(stderr, "[WARNING] Could not open CSV file '%s' for writing: %s. Continuing with console logging.\n",
            config->output_csv, strerror(errno));
    } else if (write_header) {
        fprintf(csv_fp, "timestamp,device_id,src_ip,dst_ip,src_port,dst_port,protocol,throughput,rtt,packet_loss,active_connections\n");
        fflush(csv_fp);
    }

    /* Initialize TCP Socket Client if enabled */
    socket_client_t sock_client;
    if (config->enable_socket) {
        socket_client_init(&sock_client, config->server_ip, config->server_port, config->retry_interval_sec);
        printf("[*] TCP Socket Streaming Enabled -> Controller at %s:%d\n", config->server_ip, config->server_port);
        if (socket_client_connect(&sock_client) != 0) {
            printf("[!] Controller unavailable at %s:%d. Will retry in background...\n", config->server_ip, config->server_port);
        }
    }

    printf("=========================================================\n");
    printf("Network Monitoring Agent (Phase 5)\n");
    printf("Device ID       : %s\n", config->device_id);
    printf("Interval        : %.2f sec\n", config->interval_sec);
    printf("CSV Output      : %s\n", config->output_csv);
    printf("Interface       : %s\n", config->iface_name[0] ? config->iface_name : "auto");
    if (config->enable_socket) {
        printf("Controller Host : %s:%d\n", config->server_ip, config->server_port);
    }
    printf("Status          : Running (Press Ctrl+C to stop)\n");
    printf("=========================================================\n");

    interface_stats_t prev_stats, curr_stats;
    get_interface_stats(config->iface_name, &prev_stats);

    flow_record_t flows[MAX_FLOWS_PER_SAMPLE];
    int sample_idx = 0;

    useconds_t sleep_us = (useconds_t)(config->interval_sec * 1000000.0);

    while (g_running) {
        usleep(sleep_us);
        if (!g_running) break;

        sample_idx++;

        /* 1. Calculate Throughput over interval */
        get_interface_stats(config->iface_name, &curr_stats);
        uint64_t bytes_delta = (curr_stats.rx_bytes >= prev_stats.rx_bytes) ?
                               (curr_stats.rx_bytes - prev_stats.rx_bytes) + (curr_stats.tx_bytes - prev_stats.tx_bytes) : 0;
        
        double throughput_mbps = calculate_throughput_mbps(bytes_delta, config->interval_sec);
        prev_stats = curr_stats;

        /* 2. Scan active TCP / UDP flows */
        int tcp_active = 0, udp_active = 0;
        int num_flows = scan_active_flows(
            config->device_id,
            throughput_mbps,
            flows,
            MAX_FLOWS_PER_SAMPLE,
            &tcp_active,
            &udp_active
        );

        /* 3. Output to Console */
        char ts_now[32];
        get_current_timestamp_str(ts_now, sizeof(ts_now));

        printf("\n----------------------------------------\n");
        printf("Network Monitoring Agent\n");
        printf("Device: %s\n", config->device_id);
        printf("Timestamp: %s\n", ts_now);
        printf("----------------------------------------\n");

        for (int i = 0; i < num_flows; i++) {
            flow_record_t *f = &flows[i];
            printf("\nFlow:\n");
            printf("Source IP       : %s\n", f->src_ip);
            printf("Destination IP  : %s\n", f->dst_ip);
            printf("Source Port     : %u\n", f->src_port);
            printf("Destination Port: %u\n", f->dst_port);
            printf("Protocol        : %s\n", f->protocol);
            printf("Throughput      : %.2f Mbps\n", f->throughput_mbps);
            if (f->has_rtt) {
                printf("RTT             : %.2f ms\n", f->rtt_ms);
            } else {
                printf("RTT             : N/A\n");
            }
            if (f->has_packet_loss) {
                printf("Packet Loss     : %.2f %%\n", f->packet_loss_pct);
            } else {
                printf("Packet Loss     : N/A\n");
            }

            /* 4. Append Record to CSV */
            if (csv_fp) {
                char rtt_str[16], loss_str[16];
                if (f->has_rtt) snprintf(rtt_str, sizeof(rtt_str), "%.2f", f->rtt_ms);
                else snprintf(rtt_str, sizeof(rtt_str), "N/A");

                if (f->has_packet_loss) snprintf(loss_str, sizeof(loss_str), "%.2f", f->packet_loss_pct);
                else snprintf(loss_str, sizeof(loss_str), "N/A");

                fprintf(csv_fp, "%s,%s,%s,%s,%u,%u,%s,%.2f,%s,%s,%d\n",
                    f->timestamp,
                    f->device_id,
                    f->src_ip,
                    f->dst_ip,
                    f->src_port,
                    f->dst_port,
                    f->protocol,
                    f->throughput_mbps,
                    rtt_str,
                    loss_str,
                    f->total_active_connections
                );
                fflush(csv_fp);
            }

            /* 5. Stream Record over TCP Socket to Controller if enabled */
            if (config->enable_socket) {
                if (socket_client_send_record(&sock_client, f) == 0) {
                    printf("  [->] Streamed record to controller %s:%d\n", config->server_ip, config->server_port);
                } else {
                    printf("  [!] Controller unavailable. Retrying connection...\n");
                }
            }
        }

        printf("\nActive Connections:\n");
        printf("TCP: %d\n", tcp_active);
        printf("UDP: %d\n", udp_active);
        printf("Total: %d\n", tcp_active + udp_active);
        printf("----------------------------------------\n");

        if (config->max_samples > 0 && sample_idx >= config->max_samples) {
            break;
        }
    }

    if (csv_fp) {
        fclose(csv_fp);
    }

    if (config->enable_socket) {
        socket_client_close(&sock_client);
    }

    printf("\n[*] Stopping Network Monitoring Agent for [%s]...\n", config->device_id);
    printf("[*] Monitoring records saved to: %s\n", config->output_csv);
    printf("[*] Agent shutdown cleanly.\n");

    return 0;
}

int main(int argc, char *argv[]) {
    agent_config_t config;
    if (parse_agent_args(argc, argv, &config) != 0) {
        return 1;
    }
    return run_monitoring_agent(&config);
}
