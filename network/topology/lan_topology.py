#!/usr/bin/env python3
"""
Small LAN Topology Definition for Mininet.
Simulates a small LAN with a central gateway switch and configurable client hosts (10-50).

Supports:
- Configurable host count (default: 5)
- Configurable link bandwidth (Mbps), delay (ms), jitter, and packet loss (%)
- Static IP addressing scheme (192.168.1.0/24)
- Automated connectivity tests (pingall, host-to-host)
- Interactive Mininet CLI
"""

import os
import sys

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import argparse

# Check Mininet availability
try:
    from mininet.topo import Topo
    from mininet.net import Mininet
    from mininet.node import Controller, RemoteController, OVSKernelSwitch
    from mininet.link import TCLink
    from mininet.cli import CLI
    from mininet.log import setLogLevel, info
    MININET_AVAILABLE = True
except ImportError:
    MININET_AVAILABLE = False
    # Mock base class for non-Mininet environments (macOS/CI)
    class Topo:
        def __init__(self, *args, **kwargs):
            self.hosts_list = []
            self.switches_list = []
            self.links_list = []
            self.build(*args, **kwargs)

        def addHost(self, name, **opts):
            self.hosts_list.append((name, opts))
            return name

        def addSwitch(self, name, **opts):
            self.switches_list.append((name, opts))
            return name

        def addLink(self, node1, node2, **opts):
            self.links_list.append((node1, node2, opts))

        def hosts(self):
            return [h[0] for h in self.hosts_list]

        def switches(self):
            return [s[0] for s in self.switches_list]

        def links(self, sort=True):
            return [(l[0], l[1]) for l in self.links_list]


class SmallLANTopology(Topo):
    """
    Topology representing a small LAN environment:
    
            +------------------+
            |  Gateway / Switch| (s1 / 192.168.1.1)
            +--------+---------+
                     |
         +-----------+-----------+ ... +
         |           |           |     |
      +--+---+    +--+---+    +--+---+ +--+---+
      |  h1  |    |  h2  |    |  h3  | |  hN  |
      +------+    +------+    +------+ +------+
    """

    def __init__(
        self,
        num_hosts=5,
        bw=100.0,
        delay="2ms",
        loss=0.0,
        max_queue_size=100,
        subnet="192.168.1",
        **kwargs
    ):
        self.num_hosts = max(2, min(50, num_hosts))
        self.bw = bw
        self.delay = delay
        self.loss = loss
        self.max_queue_size = max_queue_size
        self.subnet = subnet
        self.host_ip_map = {}
        super().__init__(**kwargs)

    def build(self, **kwargs):
        """Build the single-switch LAN topology with N client hosts."""
        # Central gateway / switch
        gateway = self.addSwitch("s1")

        # Create client hosts and connect to central switch
        for i in range(1, self.num_hosts + 1):
            host_name = f"h{i}"
            # Hosts get static IPs: 192.168.1.10, 192.168.1.11, etc.
            ip_addr = f"{self.subnet}.{9 + i}/24"
            mac_addr = f"00:00:00:00:00:{i:02x}"
            default_route = f"via {self.subnet}.1"

            self.addHost(
                host_name,
                ip=ip_addr,
                mac=mac_addr,
                defaultRoute=default_route
            )
            self.host_ip_map[host_name] = ip_addr.split("/")[0]

            # Connect host to switch with configured link characteristics
            self.addLink(
                host_name,
                gateway,
                bw=self.bw,
                delay=self.delay,
                loss=self.loss,
                max_queue_size=self.max_queue_size
            )

    def get_host_ip(self, host_name):
        """Return the IP address assigned to a host."""
        return self.host_ip_map.get(host_name)

    def get_all_hosts(self):
        """Return a list of all host names."""
        return [f"h{i}" for i in range(1, self.num_hosts + 1)]


def start_topology(num_hosts=5, bw=100, delay="2ms", loss=0, open_cli=True, test_mode=False):
    """Start Mininet with the SmallLANTopology."""
    if not MININET_AVAILABLE:
        print("[!] Mininet is not available in the current environment.")
        print("[i] Topology structure generated and validated in simulation mode:")
        topo = SmallLANTopology(num_hosts=num_hosts, bw=bw, delay=delay, loss=loss)
        print(f"    - Switch: {topo.switches()}")
        print(f"    - Hosts ({len(topo.hosts())}): {', '.join(topo.hosts())}")
        print(f"    - Host IPs: {topo.host_ip_map}")
        print(f"    - Link Parameters: Bandwidth={bw}Mbps, Delay={delay}, Loss={loss}%")
        return None

    setLogLevel("info")
    topo = SmallLANTopology(num_hosts=num_hosts, bw=bw, delay=delay, loss=loss)
    net = Mininet(topo=topo, link=TCLink, controller=Controller)

    print("\n" + "=" * 60)
    print(f"Starting Small LAN Topology ({num_hosts} Hosts, {bw}Mbps, {delay} delay, {loss}% loss)")
    print("=" * 60)
    net.start()

    try:
        if test_mode:
            print("\n[*] Running Automated Ping Connectivity Test...")
            loss_percent = net.pingAll()
            print(f"[*] PingAll Loss: {loss_percent}%")

            h1, h2 = net.get("h1", "h2")
            print(f"[*] Testing Host-to-Host Ping: {h1.name} ({h1.IP()}) -> {h2.name} ({h2.IP()})")
            ping_result = h1.cmd(f"ping -c 3 {h2.IP()}")
            print(ping_result)

        if open_cli:
            print("\n[*] Mininet CLI Ready. Type 'exit' to quit.")
            CLI(net)
    finally:
        print("\n[*] Stopping Mininet LAN Topology...")
        net.stop()
        print("[*] Mininet Stopped Cleanly.\n")

    return net


def main():
    parser = argparse.ArgumentParser(description="Small LAN Mininet Topology")
    parser.add_argument("--hosts", type=int, default=5, help="Number of client hosts (2-50, default: 5)")
    parser.add_argument("--bw", type=float, default=100.0, help="Link bandwidth in Mbps (default: 100.0)")
    parser.add_argument("--delay", type=str, default="2ms", help="Link propagation delay (default: 2ms)")
    parser.add_argument("--loss", type=float, default=0.0, help="Packet loss percentage (default: 0.0)")
    parser.add_argument("--test", action="store_true", help="Run automated connectivity ping tests")
    parser.add_argument("--no-cli", action="store_true", help="Do not open Mininet CLI")

    args = parser.parse_args()

    start_topology(
        num_hosts=args.hosts,
        bw=args.bw,
        delay=args.delay,
        loss=args.loss,
        open_cli=not args.no_cli,
        test_mode=args.test
    )


if __name__ == "__main__":
    main()
