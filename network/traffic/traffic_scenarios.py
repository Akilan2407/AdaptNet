"""
Predefined Traffic Generation Scenarios.
Defines 6 modular scenarios with configurable durations, bitrates, and host mappings.
"""

from typing import List
from network.traffic.config import FlowConfig, DEFAULT_DURATION, DEFAULT_UDP_BANDWIDTH


def build_scenario_tcp(duration: int = DEFAULT_DURATION, src: str = "h1", dst: str = "h2", port: int = 5201) -> List[FlowConfig]:
    """Scenario 1: Normal single TCP flow."""
    return [
        FlowConfig(
            flow_id="flow_tcp_1",
            src_host=src,
            dst_host=dst,
            protocol="tcp",
            duration=duration,
            port=port,
            description="Scenario 1: Normal Single TCP Stream"
        )
    ]


def build_scenario_udp(duration: int = DEFAULT_DURATION, bandwidth: str = DEFAULT_UDP_BANDWIDTH, src: str = "h3", dst: str = "h4", port: int = 5202) -> List[FlowConfig]:
    """Scenario 2: Normal single UDP flow."""
    return [
        FlowConfig(
            flow_id="flow_udp_1",
            src_host=src,
            dst_host=dst,
            protocol="udp",
            duration=duration,
            bandwidth=bandwidth,
            port=port,
            description=f"Scenario 2: Normal Single UDP Stream ({bandwidth})"
        )
    ]


def build_scenario_multi_tcp(duration: int = DEFAULT_DURATION, port_base: int = 5201) -> List[FlowConfig]:
    """Scenario 3: Multiple concurrent TCP flows across different hosts."""
    return [
        FlowConfig(
            flow_id="multi_tcp_1",
            src_host="h1",
            dst_host="h2",
            protocol="tcp",
            duration=duration,
            port=port_base,
            description="TCP Stream 1: h1 -> h2"
        ),
        FlowConfig(
            flow_id="multi_tcp_2",
            src_host="h3",
            dst_host="h4",
            protocol="tcp",
            duration=duration,
            port=port_base + 1,
            description="TCP Stream 2: h3 -> h4"
        ),
        FlowConfig(
            flow_id="multi_tcp_3",
            src_host="h5",
            dst_host="h2",
            protocol="tcp",
            duration=duration,
            port=port_base + 2,
            description="TCP Stream 3: h5 -> h2"
        )
    ]


def build_scenario_multi_udp(duration: int = DEFAULT_DURATION, bandwidth: str = "8M", port_base: int = 5210) -> List[FlowConfig]:
    """Scenario 4: Multiple concurrent UDP flows."""
    return [
        FlowConfig(
            flow_id="multi_udp_1",
            src_host="h1",
            dst_host="h2",
            protocol="udp",
            duration=duration,
            bandwidth=bandwidth,
            port=port_base,
            description=f"UDP Stream 1: h1 -> h2 ({bandwidth})"
        ),
        FlowConfig(
            flow_id="multi_udp_2",
            src_host="h3",
            dst_host="h4",
            protocol="udp",
            duration=duration,
            bandwidth=bandwidth,
            port=port_base + 1,
            description=f"UDP Stream 2: h3 -> h4 ({bandwidth})"
        ),
        FlowConfig(
            flow_id="multi_udp_3",
            src_host="h5",
            dst_host="h1",
            protocol="udp",
            duration=duration,
            bandwidth=bandwidth,
            port=port_base + 2,
            description=f"UDP Stream 3: h5 -> h1 ({bandwidth})"
        )
    ]


def build_scenario_mixed(duration: int = DEFAULT_DURATION, udp_bw: str = "12M", port_base: int = 5220) -> List[FlowConfig]:
    """Scenario 5: Mixed simultaneous TCP and UDP flows."""
    return [
        FlowConfig(
            flow_id="mixed_tcp_1",
            src_host="h1",
            dst_host="h2",
            protocol="tcp",
            duration=duration,
            port=port_base,
            description="Mixed Flow 1 (TCP): h1 -> h2"
        ),
        FlowConfig(
            flow_id="mixed_udp_2",
            src_host="h3",
            dst_host="h4",
            protocol="udp",
            duration=duration,
            bandwidth=udp_bw,
            port=port_base + 1,
            description=f"Mixed Flow 2 (UDP): h3 -> h4 ({udp_bw})"
        ),
        FlowConfig(
            flow_id="mixed_tcp_3",
            src_host="h5",
            dst_host="h2",
            protocol="tcp",
            duration=duration,
            port=port_base + 2,
            description="Mixed Flow 3 (TCP): h5 -> h2"
        ),
        FlowConfig(
            flow_id="mixed_udp_4",
            src_host="h4",
            dst_host="h1",
            protocol="udp",
            duration=duration,
            bandwidth=udp_bw,
            port=port_base + 3,
            description=f"Mixed Flow 4 (UDP): h4 -> h1 ({udp_bw})"
        )
    ]


def build_scenario_congestion(duration: int = DEFAULT_DURATION, high_bw: str = "80M", port_base: int = 5230) -> List[FlowConfig]:
    """
    Scenario 6: Congestion-like traffic with multiple high-bandwidth flows
    generating high link utilization.
    """
    return [
        FlowConfig(
            flow_id="congest_bulk_tcp_1",
            src_host="h1",
            dst_host="h2",
            protocol="tcp",
            duration=duration,
            port=port_base,
            parallel=4,
            description="Congestion Flow 1: Bulk Multi-stream TCP (h1 -> h2)"
        ),
        FlowConfig(
            flow_id="congest_flood_udp_2",
            src_host="h3",
            dst_host="h2",
            protocol="udp",
            duration=duration,
            bandwidth=high_bw,
            port=port_base + 1,
            description=f"Congestion Flow 2: High-Bitrate UDP Flood ({high_bw}) (h3 -> h2)"
        ),
        FlowConfig(
            flow_id="congest_bulk_tcp_3",
            src_host="h4",
            dst_host="h2",
            protocol="tcp",
            duration=duration,
            port=port_base + 2,
            parallel=2,
            description="Congestion Flow 3: Secondary Bulk TCP (h4 -> h2)"
        ),
        FlowConfig(
            flow_id="congest_flood_udp_4",
            src_host="h5",
            dst_host="h2",
            protocol="udp",
            duration=duration,
            bandwidth=high_bw,
            port=port_base + 3,
            description=f"Congestion Flow 4: High-Bitrate UDP Burst ({high_bw}) (h5 -> h2)"
        )
    ]


SCENARIO_BUILDERS = {
    "tcp": build_scenario_tcp,
    "udp": build_scenario_udp,
    "multi_tcp": build_scenario_multi_tcp,
    "multi_udp": build_scenario_multi_udp,
    "mixed": build_scenario_mixed,
    "congestion": build_scenario_congestion,
}


def get_scenario_flows(
    scenario_name: str,
    duration: int = DEFAULT_DURATION,
    bandwidth: str = DEFAULT_UDP_BANDWIDTH,
    src: str = "h1",
    dst: str = "h2"
) -> List[FlowConfig]:
    """Retrieve and instantiate flow configurations for a named scenario."""
    name = scenario_name.lower().strip()
    if name not in SCENARIO_BUILDERS:
        valid_options = ", ".join(SCENARIO_BUILDERS.keys())
        raise ValueError(f"Unknown scenario '{scenario_name}'. Available: {valid_options}")

    builder = SCENARIO_BUILDERS[name]
    if name == "tcp":
        return builder(duration=duration, src=src, dst=dst)
    elif name == "udp":
        return builder(duration=duration, bandwidth=bandwidth, src=src, dst=dst)
    elif name in ["multi_udp", "mixed"]:
        return builder(duration=duration, **({"bandwidth": bandwidth} if name == "multi_udp" else {"udp_bw": bandwidth}))
    elif name == "congestion":
        return builder(duration=duration, high_bw=bandwidth)
    else:
        return builder(duration=duration)
