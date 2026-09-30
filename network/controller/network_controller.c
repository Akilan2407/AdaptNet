#include "network_controller.h"
#include "client_handler.h"
#include "data_ingestion.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

static volatile sig_atomic_t g_controller_running = 1;
static int g_server_fd = -1;

static void handle_sigint(int sig) {
    (void)sig;
    g_controller_running = 0;
    if (g_server_fd >= 0) {
        close(g_server_fd);
        g_server_fd = -1;
    }
}

static void print_usage(const char *prog_name) {
    printf("Usage: %s [OPTIONS]\n\n", prog_name);
    printf("Options:\n");
    printf("  --port <port>         Port to listen on (default: %d)\n", DEFAULT_CONTROLLER_LISTEN_PORT);
    printf("  --bind <ip>           IP address to bind to (default: %s)\n", DEFAULT_CONTROLLER_BIND_IP);
    printf("  --buffer-size <N>     In-memory circular ring buffer capacity (default: 1000)\n");
    printf("  --output <csv_file>   CSV output path for validated records (default: %s)\n", DEFAULT_METRICS_CSV);
    printf("  --jsonl <jsonl_file>  JSON Lines output path (default: %s)\n", DEFAULT_METRICS_JSONL);
    printf("  --invalid-log <file>  Invalid/rejected records log path (default: %s)\n", DEFAULT_INVALID_LOG);
    printf("  --help, -h            Display this help message\n");
}

int parse_controller_args(int argc, char *argv[], controller_config_t *config) {
    if (!config) return -1;

    memset(config, 0, sizeof(controller_config_t));
    snprintf(config->bind_ip, sizeof(config->bind_ip), "%s", DEFAULT_CONTROLLER_BIND_IP);
    config->port = DEFAULT_CONTROLLER_LISTEN_PORT;
    config->buffer_size = DEFAULT_BUFFER_CAPACITY;
    snprintf(config->output_csv, sizeof(config->output_csv), "%s", DEFAULT_METRICS_CSV);
    snprintf(config->output_jsonl, sizeof(config->output_jsonl), "%s", DEFAULT_METRICS_JSONL);
    snprintf(config->invalid_log, sizeof(config->invalid_log), "%s", DEFAULT_INVALID_LOG);
    config->verbose = 1;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--help") == 0 || strcmp(argv[i], "-h") == 0) {
            print_usage(argv[0]);
            exit(0);
        } else if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
            config->port = atoi(argv[++i]);
            if (config->port <= 0 || config->port > 65535) {
                fprintf(stderr, "[ERROR] Invalid port: %s\n", argv[i]);
                return -1;
            }
        } else if (strcmp(argv[i], "--bind") == 0 && i + 1 < argc) {
            snprintf(config->bind_ip, sizeof(config->bind_ip), "%s", argv[++i]);
        } else if (strcmp(argv[i], "--buffer-size") == 0 && i + 1 < argc) {
            config->buffer_size = (size_t)atoi(argv[++i]);
            if (config->buffer_size == 0) config->buffer_size = DEFAULT_BUFFER_CAPACITY;
        } else if (strcmp(argv[i], "--output") == 0 && i + 1 < argc) {
            snprintf(config->output_csv, sizeof(config->output_csv), "%s", argv[++i]);
        } else if (strcmp(argv[i], "--jsonl") == 0 && i + 1 < argc) {
            snprintf(config->output_jsonl, sizeof(config->output_jsonl), "%s", argv[++i]);
        } else if (strcmp(argv[i], "--invalid-log") == 0 && i + 1 < argc) {
            snprintf(config->invalid_log, sizeof(config->invalid_log), "%s", argv[++i]);
        } else {
            fprintf(stderr, "[ERROR] Unknown option '%s'\n", argv[i]);
            print_usage(argv[0]);
            return -1;
        }
    }
    return 0;
}

int run_network_controller(const controller_config_t *config) {
    if (!config) return -1;

    /* Signal setup */
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = handle_sigint;
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    /* Initialize Data Ingestion Pipeline */
    if (data_ingestion_init(config->buffer_size, config->output_csv, config->output_jsonl, config->invalid_log) != 0) {
        fprintf(stderr, "[!] Failed to initialize Data Ingestion Pipeline\n");
        return -1;
    }

    pthread_mutex_t console_mutex = PTHREAD_MUTEX_INITIALIZER;

    /* Create TCP socket */
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        fprintf(stderr, "[!] Socket creation failed: %s\n", strerror(errno));
        data_ingestion_destroy();
        return -1;
    }
    g_server_fd = server_fd;

    /* Enable SO_REUSEADDR */
    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        fprintf(stderr, "[!] setsockopt(SO_REUSEADDR) failed: %s\n", strerror(errno));
    }

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons((uint16_t)config->port);

    if (strcmp(config->bind_ip, "0.0.0.0") == 0) {
        serv_addr.sin_addr.s_addr = INADDR_ANY;
    } else {
        if (inet_pton(AF_INET, config->bind_ip, &serv_addr.sin_addr) <= 0) {
            fprintf(stderr, "[!] Invalid bind IP: '%s'\n", config->bind_ip);
            close(server_fd);
            data_ingestion_destroy();
            return -1;
        }
    }

    /* Bind */
    if (bind(server_fd, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        fprintf(stderr, "[!] Bind to %s:%d failed: %s\n", config->bind_ip, config->port, strerror(errno));
        close(server_fd);
        data_ingestion_destroy();
        return -1;
    }

    /* Listen */
    if (listen(server_fd, MAX_PENDING_CONNECTIONS) < 0) {
        fprintf(stderr, "[!] Listen failed: %s\n", strerror(errno));
        close(server_fd);
        data_ingestion_destroy();
        return -1;
    }

    printf("=========================================================\n");
    printf("C Network Controller & Data Ingestion Hub (Phase 6)\n");
    printf("Listening On    : %s:%d\n", config->bind_ip, config->port);
    printf("Buffer Capacity : %zu records\n", config->buffer_size);
    printf("CSV Storage     : %s\n", config->output_csv);
    printf("JSONL Storage   : %s\n", config->output_jsonl);
    printf("Invalid Log     : %s\n", config->invalid_log);
    printf("Status          : Ingestion Active (Ctrl+C to quit)\n");
    printf("=========================================================\n");

    while (g_controller_running) {
        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        int client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);

        if (client_fd < 0) {
            if (!g_controller_running) break;
            if (errno == EINTR) continue;
            fprintf(stderr, "[!] Accept error: %s\n", strerror(errno));
            continue;
        }

        client_context_t *ctx = (client_context_t *)malloc(sizeof(client_context_t));
        if (!ctx) {
            fprintf(stderr, "[!] Memory allocation failure for client\n");
            close(client_fd);
            continue;
        }

        memset(ctx, 0, sizeof(client_context_t));
        ctx->client_fd = client_fd;
        inet_ntop(AF_INET, &client_addr.sin_addr, ctx->client_ip, sizeof(ctx->client_ip));
        ctx->client_port = ntohs(client_addr.sin_port);
        ctx->csv_fp = NULL;
        ctx->csv_mutex = NULL;
        ctx->console_mutex = &console_mutex;

        start_client_handler(ctx);
    }

    printf("\n[*] Shutting down C Network Controller & Ingestion Engine...\n");
    if (server_fd >= 0) {
        close(server_fd);
    }

    data_ingestion_print_stats();
    data_ingestion_destroy();

    printf("[*] Controller & Ingestion Engine stopped cleanly.\n");
    return 0;
}

int main(int argc, char *argv[]) {
    controller_config_t config;
    if (parse_controller_args(argc, argv, &config) != 0) {
        return 1;
    }
    return run_network_controller(&config);
}
