"""Real-time Packet Capture and ML Inference Engine for AdaptNet.

Integrates:
1. Packet Normalization (from network/agent/packet_sniffer.py)
2. Real-Time Flow Aggregation (5-tuple, byte/packet counts, Mbps, Loss, RTT)
3. Feature Extraction (matching trained ML model schemas)
4. Trained Model Inference:
   - Traffic Classification (Phase 12 rules)
   - K-Means Device Behavioral Profiling (Phase 8 clustering)
   - GRU Neural Network Congestion Forecasting (Phase 10 sequential model)
5. QoS Policy Decision Engine (Phase 13 explainable priority evaluation)
6. Decision Traces (Phase 15 7-stage lineage)
"""

from ml.realtime.packet_normalizer import PacketNormalizer, NormalizedPacket
from ml.realtime.flow_aggregator import RealTimeFlowAggregator, AggregatedFlow
from ml.realtime.model_runner import RealTimeModelRunner
from ml.realtime.pipeline_manager import RealTimePipelineManager, pipeline_manager

__all__ = [
    "PacketNormalizer",
    "NormalizedPacket",
    "RealTimeFlowAggregator",
    "AggregatedFlow",
    "RealTimeModelRunner",
    "RealTimePipelineManager",
    "pipeline_manager",
]
