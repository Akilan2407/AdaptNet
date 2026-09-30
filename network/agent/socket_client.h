#ifndef SOCKET_CLIENT_H
#define SOCKET_CLIENT_H

#include <stddef.h>
#include <stdint.h>
#include "flow_monitor.h"

#define MAX_LINE_BUF_LEN 512
#define DEFAULT_CONTROLLER_IP "127.0.0.1"
#define DEFAULT_CONTROLLER_PORT 5000
#define DEFAULT_RETRY_INTERVAL_SEC 2.0

typedef struct {
    char server_ip[64];
    int server_port;
    int sock_fd;
    int is_connected;
    double retry_interval_sec;
} socket_client_t;

/* Initialize socket client configuration */
int socket_client_init(socket_client_t *client, const char *server_ip, int server_port, double retry_interval_sec);

/* Attempt TCP connection to controller (non-blocking / error handled) */
int socket_client_connect(socket_client_t *client);

/* Ensure all bytes are sent across TCP stream (handles partial sends) */
int socket_client_send_all(int sock_fd, const char *buffer, size_t length);

/* Serialize flow_record_t into pipe-delimited line format ending in \n */
int serialize_flow_record(const flow_record_t *rec, char *out_buf, size_t max_len);

/* Send flow record over active TCP socket (attempts reconnect if disconnected) */
int socket_client_send_record(socket_client_t *client, const flow_record_t *rec);

/* Close socket and reset connection state */
void socket_client_close(socket_client_t *client);

#endif /* SOCKET_CLIENT_H */
