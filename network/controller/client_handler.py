"""Worker thread and socket connection handler for incoming monitoring agent telemetry (converted from client_handler.h/.c)."""

import socket
import threading
from typing import Optional

from network.ingestion.data_ingestion import data_ingestion_process_raw_line


_console_lock = threading.Lock()


def process_received_line(line: str, client_ip: str, client_port: int) -> int:
    """Process a single line-delimited flow record and print formatted details."""
    if not line:
        return -1

    client_addr_str = f"{client_ip}:{client_port}"
    res = data_ingestion_process_raw_line(line, client_addr_str)

    tokens = line.split("|")
    if len(tokens) in (11, 16) and res == 0:
        with _console_lock:
            rtt_val = tokens[8]
            rtt_str = rtt_val
            if rtt_val != "N/A" and "m" not in rtt_val:
                rtt_str = f"{rtt_val} ms"

            loss_val = tokens[9]
            loss_str = loss_val
            if loss_val != "N/A" and "%" not in loss_val:
                loss_str = f"{loss_val} %"

            print("\n========================================")
            print("C NETWORK CONTROLLER")
            print("========================================")
            print("\nAgent Stream Active:")
            print(f"Device: {tokens[1]}")
            print(f"Address: {client_ip}:{client_port}")
            print("\nReceived Flow Record")
            print("----------------------------------------")
            print(f"Timestamp        : {tokens[0]}")
            print(f"Device ID        : {tokens[1]}")
            print(f"Source IP        : {tokens[2]}")
            print(f"Destination IP   : {tokens[3]}")
            print(f"Source Port      : {tokens[4]}")
            print(f"Destination Port : {tokens[5]}")
            print(f"Protocol         : {tokens[6]}")
            print(f"Throughput       : {tokens[7]} Mbps")
            print(f"RTT              : {rtt_str}")
            print(f"Packet Loss      : {loss_str}")
            print(f"Active Connections: {tokens[10]}")
            print("----------------------------------------")

    return res


def handle_client_connection(client_sock: socket.socket, client_addr: tuple) -> None:
    """Read streaming line-delimited records from a connected agent socket."""
    client_ip, client_port = client_addr[0], client_addr[1]
    with _console_lock:
        print(f"\n[+] Agent connected: {client_ip}:{client_port} (Socket FD {client_sock.fileno()})")

    buffer = ""
    try:
        while True:
            data = client_sock.recv(1024)
            if not data:
                break

            chunk = data.decode("utf-8", errors="replace")
            buffer += chunk

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip("\r\n")
                if line:
                    process_received_line(line, client_ip, client_port)
    except Exception:
        pass
    finally:
        with _console_lock:
            print(f"\n[-] Agent disconnected: {client_ip}:{client_port}")
        try:
            client_sock.close()
        except Exception:
            pass


def start_client_handler(client_sock: socket.socket, client_addr: tuple) -> threading.Thread:
    """Spawn daemon thread to handle connected agent."""
    t = threading.Thread(target=handle_client_connection, args=(client_sock, client_addr), daemon=True)
    t.start()
    return t
