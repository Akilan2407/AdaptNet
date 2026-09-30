#include "socket_client.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>

int socket_client_init(socket_client_t *client, const char *server_ip, int server_port, double retry_interval_sec) {
    if (!client) return -1;
    memset(client, 0, sizeof(socket_client_t));
    snprintf(client->server_ip, sizeof(client->server_ip), "%s", (server_ip && server_ip[0]) ? server_ip : DEFAULT_CONTROLLER_IP);
    client->server_port = (server_port > 0) ? server_port : DEFAULT_CONTROLLER_PORT;
    client->sock_fd = -1;
    client->is_connected = 0;
    client->retry_interval_sec = (retry_interval_sec > 0.0) ? retry_interval_sec : DEFAULT_RETRY_INTERVAL_SEC;
    return 0;
}

int socket_client_connect(socket_client_t *client) {
    if (!client) return -1;
    if (client->is_connected && client->sock_fd >= 0) {
        return 0;
    }

    if (client->sock_fd >= 0) {
        close(client->sock_fd);
        client->sock_fd = -1;
    }

    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) {
        fprintf(stderr, "[!] Socket creation failed: %s\n", strerror(errno));
        return -1;
    }

#ifdef SO_NOSIGPIPE
    int opt = 1;
    setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &opt, sizeof(opt));
#endif

    struct sockaddr_in serv_addr;
    memset(&serv_addr, 0, sizeof(serv_addr));
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons((uint16_t)client->server_port);

    if (inet_pton(AF_INET, client->server_ip, &serv_addr.sin_addr) <= 0) {
        fprintf(stderr, "[!] Invalid server address: '%s'\n", client->server_ip);
        close(fd);
        return -1;
    }

    if (connect(fd, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        /* Connection failed */
        close(fd);
        client->sock_fd = -1;
        client->is_connected = 0;
        return -1;
    }

    client->sock_fd = fd;
    client->is_connected = 1;
    printf("[+] Connected to controller %s:%d\n", client->server_ip, client->server_port);
    return 0;
}

int socket_client_send_all(int sock_fd, const char *buffer, size_t length) {
    if (sock_fd < 0 || !buffer || length == 0) return -1;

    size_t total_sent = 0;
    while (total_sent < length) {
#ifdef MSG_NOSIGNAL
        ssize_t sent = send(sock_fd, buffer + total_sent, length - total_sent, MSG_NOSIGNAL);
#else
        ssize_t sent = send(sock_fd, buffer + total_sent, length - total_sent, 0);
#endif
        if (sent < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (sent == 0) {
            return -1; /* Connection closed */
        }
        total_sent += (size_t)sent;
    }
    return 0;
}

int serialize_flow_record(const flow_record_t *rec, char *out_buf, size_t max_len) {
    if (!rec || !out_buf || max_len == 0) return -1;

    char rtt_str[32];
    char loss_str[32];

    if (rec->has_rtt) {
        snprintf(rtt_str, sizeof(rtt_str), "%.2f", rec->rtt_ms);
    } else {
        snprintf(rtt_str, sizeof(rtt_str), "N/A");
    }

    if (rec->has_packet_loss) {
        snprintf(loss_str, sizeof(loss_str), "%.2f", rec->packet_loss_pct);
    } else {
        snprintf(loss_str, sizeof(loss_str), "N/A");
    }

    /*
     * Protocol Schema:
     * timestamp|device_id|src_ip|dst_ip|src_port|dst_port|protocol|throughput|rtt|packet_loss|active_connections\n
     */
    int written = snprintf(out_buf, max_len,
        "%s|%s|%s|%s|%u|%u|%s|%.2f|%s|%s|%d\n",
        rec->timestamp,
        rec->device_id,
        rec->src_ip,
        rec->dst_ip,
        rec->src_port,
        rec->dst_port,
        rec->protocol,
        rec->throughput_mbps,
        rtt_str,
        loss_str,
        rec->total_active_connections
    );

    if (written < 0 || (size_t)written >= max_len) {
        return -1;
    }
    return written;
}

int socket_client_send_record(socket_client_t *client, const flow_record_t *rec) {
    if (!client || !rec) return -1;

    /* If not connected, attempt reconnect */
    if (!client->is_connected || client->sock_fd < 0) {
        if (socket_client_connect(client) != 0) {
            return -1;
        }
    }

    char line_buf[MAX_LINE_BUF_LEN];
    int len = serialize_flow_record(rec, line_buf, sizeof(line_buf));
    if (len <= 0) return -1;

    if (socket_client_send_all(client->sock_fd, line_buf, (size_t)len) != 0) {
        fprintf(stderr, "[!] Socket send failed: %s. Marking disconnected.\n", strerror(errno));
        socket_client_close(client);
        return -1;
    }

    return 0;
}

void socket_client_close(socket_client_t *client) {
    if (!client) return;
    if (client->sock_fd >= 0) {
        close(client->sock_fd);
        client->sock_fd = -1;
    }
    client->is_connected = 0;
}
