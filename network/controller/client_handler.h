#ifndef CLIENT_HANDLER_H
#define CLIENT_HANDLER_H

#include <stdio.h>
#include <stddef.h>
#include <stdint.h>
#include <pthread.h>
#include <netinet/in.h>

#define MAX_LINE_LEN 1024
#define MAX_ACCUM_BUF 4096

typedef struct {
    int client_fd;
    char client_ip[INET_ADDRSTRLEN];
    uint16_t client_port;
    pthread_t thread_id;
    FILE *csv_fp;
    pthread_mutex_t *csv_mutex;
    pthread_mutex_t *console_mutex;
    volatile int is_active;
} client_context_t;

/* Start worker thread for accepted client connection */
int start_client_handler(client_context_t *ctx);

/* Parse and validate a single line-delimited flow record */
int process_received_line(client_context_t *ctx, const char *line);

#endif /* CLIENT_HANDLER_H */
