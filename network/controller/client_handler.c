#include "client_handler.h"
#include "data_ingestion.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/socket.h>
#include <arpa/inet.h>

int process_received_line(client_context_t *ctx, const char *line) {
    if (!ctx || !line || line[0] == '\0') return -1;

    char client_addr_str[64];
    snprintf(client_addr_str, sizeof(client_addr_str), "%s:%u", ctx->client_ip, ctx->client_port);

    /* Process through Phase 6 Ingestion Pipeline (Parse -> Validate -> Deduplicate -> Store) */
    int res = data_ingestion_process_raw_line(line, client_addr_str);

    /* Also format display for console */
    char buffer[MAX_LINE_LEN];
    snprintf(buffer, sizeof(buffer), "%s", line);

    char *tokens[16];
    int token_count = 0;
    char *saveptr = NULL;
    char *tok = strtok_r(buffer, "|", &saveptr);

    while (tok && token_count < 16) {
        tokens[token_count++] = tok;
        tok = strtok_r(NULL, "|", &saveptr);
    }

    if (token_count == 11 && res == 0) {
        pthread_mutex_lock(ctx->console_mutex);
        printf("\n========================================\n");
        printf("C NETWORK CONTROLLER\n");
        printf("========================================\n");
        printf("\nAgent Stream Active:\n");
        printf("Device: %s\n", tokens[1]);
        printf("Address: %s:%u\n", ctx->client_ip, ctx->client_port);
        printf("\nReceived Flow Record\n");
        printf("----------------------------------------\n");
        printf("Timestamp        : %s\n", tokens[0]);
        printf("Device ID        : %s\n", tokens[1]);
        printf("Source IP        : %s\n", tokens[2]);
        printf("Destination IP   : %s\n", tokens[3]);
        printf("Source Port      : %s\n", tokens[4]);
        printf("Destination Port : %s\n", tokens[5]);
        printf("Protocol         : %s\n", tokens[6]);
        printf("Throughput       : %s Mbps\n", tokens[7]);
        printf("RTT              : %s%s\n", tokens[8], (strcmp(tokens[8], "N/A") != 0 && !strchr(tokens[8], 'm')) ? " ms" : "");
        printf("Packet Loss      : %s%s\n", tokens[9], (strcmp(tokens[9], "N/A") != 0 && !strchr(tokens[9], '%')) ? " %" : "");
        printf("Active Connections: %s\n", tokens[10]);
        printf("----------------------------------------\n");
        pthread_mutex_unlock(ctx->console_mutex);
    }

    return res;
}

static void *client_worker(void *arg) {
    client_context_t *ctx = (client_context_t *)arg;
    char rx_buf[1024];
    char accum[MAX_ACCUM_BUF];
    size_t accum_len = 0;

    pthread_mutex_lock(ctx->console_mutex);
    printf("\n[+] Agent connected: %s:%u (Socket FD %d)\n", ctx->client_ip, ctx->client_port, ctx->client_fd);
    pthread_mutex_unlock(ctx->console_mutex);

    while (ctx->is_active) {
        ssize_t bytes_recv = recv(ctx->client_fd, rx_buf, sizeof(rx_buf) - 1, 0);
        if (bytes_recv <= 0) {
            /* 0 = graceful disconnect, <0 = error */
            break;
        }

        rx_buf[bytes_recv] = '\0';

        /* Accumulate received chunks */
        if (accum_len + (size_t)bytes_recv < sizeof(accum) - 1) {
            memcpy(accum + accum_len, rx_buf, (size_t)bytes_recv);
            accum_len += (size_t)bytes_recv;
            accum[accum_len] = '\0';
        } else {
            /* Buffer overflow guard: reset buffer */
            accum_len = 0;
            accum[0] = '\0';
            continue;
        }

        /* Scan for complete newline-terminated records */
        char *line_start = accum;
        char *nl_ptr;

        while ((nl_ptr = strchr(line_start, '\n')) != NULL) {
            *nl_ptr = '\0'; /* Null terminate the complete line */
            
            /* Trim carriage return if present */
            size_t line_len = strlen(line_start);
            if (line_len > 0 && line_start[line_len - 1] == '\r') {
                line_start[line_len - 1] = '\0';
            }

            if (line_start[0] != '\0') {
                process_received_line(ctx, line_start);
            }

            line_start = nl_ptr + 1;
        }

        /* Shift any remaining partial record to the beginning of accum */
        size_t processed_len = (size_t)(line_start - accum);
        if (processed_len < accum_len) {
            size_t remaining = accum_len - processed_len;
            memmove(accum, line_start, remaining);
            accum_len = remaining;
            accum[accum_len] = '\0';
        } else {
            accum_len = 0;
            accum[0] = '\0';
        }
    }

    pthread_mutex_lock(ctx->console_mutex);
    printf("\n[-] Agent disconnected: %s:%u\n", ctx->client_ip, ctx->client_port);
    pthread_mutex_unlock(ctx->console_mutex);

    close(ctx->client_fd);
    ctx->client_fd = -1;
    ctx->is_active = 0;
    free(ctx);
    return NULL;
}

int start_client_handler(client_context_t *ctx) {
    if (!ctx) return -1;
    ctx->is_active = 1;
    if (pthread_create(&ctx->thread_id, NULL, client_worker, ctx) != 0) {
        fprintf(stderr, "[!] Failed to spawn worker thread for client: %s\n", strerror(errno));
        close(ctx->client_fd);
        free(ctx);
        return -1;
    }
    pthread_detach(ctx->thread_id);
    return 0;
}
