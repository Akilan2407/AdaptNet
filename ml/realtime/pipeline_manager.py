"""Real-Time ML Pipeline Manager.

Coordinates the end-to-end processing pipeline:
Packet Sniffer -> Live Packet Queue -> Flow Aggregator -> Feature Extraction -> Model Inference -> QoS Decision -> Decision Trace -> Dashboard.

Ensures thread-safe execution, bounded memory buffers, non-blocking queue ingestion,
and safe lifecycle management (preventing duplicate workers).
"""

from collections import defaultdict, deque
import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ml.realtime.flow_aggregator import AggregatedFlow, RealTimeFlowAggregator
from ml.realtime.model_runner import RealTimeModelRunner
from ml.realtime.packet_normalizer import NormalizedPacket, PacketNormalizer

logger = logging.getLogger("ml.realtime.pipeline_manager")

QUEUE_MAX_SIZE = 5000
RING_BUFFER_SIZE = 500


class RealTimePipelineManager:
    """Singleton coordinator for the real-time packet-to-prediction pipeline."""

    def __init__(self, max_buffer: int = RING_BUFFER_SIZE) -> None:
        self.max_buffer = max_buffer

        self.normalizer = PacketNormalizer()
        self.flow_aggregator = RealTimeFlowAggregator(
            idle_timeout_seconds=15.0,
            max_active_flows=1000,
            update_interval_seconds=1.0,
            on_flow_update=self._handle_flow_update,
        )
        self.model_runner = RealTimeModelRunner()

        # Threading and Queues
        self._lock = threading.Lock()
        self._packet_queue: queue.Queue = queue.Queue(maxsize=QUEUE_MAX_SIZE)
        self._worker_thread: Optional[threading.Thread] = None
        self._is_running: bool = False
        self._stop_event = threading.Event()

        # Bounded Ring Buffers for Live Dashboard Queries
        self._recent_packets: deque = deque(maxlen=max_buffer)
        self._recent_flows: deque = deque(maxlen=max_buffer)
        self._recent_predictions: deque = deque(maxlen=max_buffer)
        self._recent_traces: deque = deque(maxlen=max_buffer)

        # Pipeline Performance Counters
        self._total_packets_received: int = 0
        self._total_packets_dropped: int = 0
        self._total_inferences: int = 0
        self._start_time: Optional[float] = None
        self._last_inference_time: Optional[float] = None
        self._error_count: int = 0
        self._last_error: Optional[str] = None

        # Live Analytics Distribution Counters
        self._class_distribution: Dict[str, int] = defaultdict(int)
        self._congestion_distribution: Dict[str, int] = defaultdict(int)
        self._priority_distribution: Dict[str, int] = defaultdict(int)

    # ── Queue Ingestion (Called from PacketSniffer callback) ──────────────────

    def enqueue_packet(self, pkt: Any) -> bool:
        """Enqueue a captured packet from the sniffer without blocking.

        Args:
            pkt: CapturedPacket instance or raw packet dictionary.

        Returns:
            True if queued successfully, False if dropped due to queue congestion.
        """
        with self._lock:
            self._total_packets_received += 1

        try:
            self._packet_queue.put_nowait(pkt)
            return True
        except queue.Full:
            with self._lock:
                self._total_packets_dropped += 1
            return False

    # ── Worker Thread Execution ──────────────────────────────────────────────

    def _pipeline_worker_loop(self) -> None:
        """Background thread consuming packets, updating flows, and executing ML inference."""
        logger.info("Real-time ML pipeline worker thread started.")
        last_prune_time = time.time()

        while not self._stop_event.is_set():
            try:
                pkt_raw = self._packet_queue.get(timeout=0.25)
            except queue.Empty:
                # Idle tick: check if idle flows should be pruned
                now = time.time()
                if now - last_prune_time > 2.0:
                    pruned = self.flow_aggregator.prune_idle_flows(now)
                    for flow in pruned:
                        self._run_inference_on_flow(flow)
                    last_prune_time = now
                continue

            try:
                # 1. Packet Normalization
                norm_pkt = self.normalizer.normalize(pkt_raw)
                with self._lock:
                    self._recent_packets.append(norm_pkt.to_dict())

                # 2. Flow Aggregation & Immediate/Periodic Inference
                flow = self.flow_aggregator.add_packet(norm_pkt)
                if flow is not None and (flow.packet_count == 1 or flow.packet_count % 10 == 0):
                    self._run_inference_on_flow(flow)

            except Exception as e:
                logger.error("Pipeline worker packet processing error: %s", e)
                with self._lock:
                    self._error_count += 1
                    self._last_error = str(e)
            finally:
                self._packet_queue.task_done()

        logger.info("Real-time ML pipeline worker thread terminated cleanly.")

    def _handle_flow_update(self, flow: AggregatedFlow) -> None:
        """Callback invoked when a flow reaches an update threshold."""
        self._run_inference_on_flow(flow)

    def _run_inference_on_flow(self, flow: AggregatedFlow) -> None:
        """Execute ML inference stages on an aggregated flow and update live state."""
        try:
            # 3. Model Inference & Decision Trace
            trace = self.model_runner.process_flow(flow)

            tc = trace["traffic_classification"]
            cf = trace["congestion_forecast"]
            qos = trace["qos_decision"]
            prof = trace["user_profiling"]

            with self._lock:
                self._total_inferences += 1
                self._last_inference_time = time.time()

                # Add to trace buffer
                self._recent_traces.append(trace)

                # Add to flows buffer
                flow_dict = flow.to_dict()
                flow_dict["traffic_class"] = tc["traffic_class"]
                flow_dict["predicted_congestion_score"] = cf["predicted_congestion_score"]
                flow_dict["predicted_congestion_class"] = cf["predicted_congestion_class"]
                flow_dict["cluster_id"] = prof["cluster_id"]
                flow_dict["final_priority"] = qos["final_priority"]
                flow_dict["trace_id"] = trace["trace_id"]
                self._recent_flows.append(flow_dict)

                # Add to predictions buffer
                pred_entry = {
                    "trace_id": trace["trace_id"],
                    "timestamp": trace["timestamp"],
                    "flow_id": flow.flow_id,
                    "device_id": flow.device_id,
                    "src_ip": flow.src_ip,
                    "dst_ip": flow.dst_ip,
                    "traffic_class": tc["traffic_class"],
                    "classification_confidence": tc["confidence"],
                    "predicted_congestion_score": cf["predicted_congestion_score"],
                    "predicted_congestion_class": cf["predicted_congestion_class"],
                    "congestion_confidence": cf["confidence"],
                    "cluster_id": prof["cluster_id"],
                    "profile_label": prof["profile_label"],
                    "final_priority": qos["final_priority"],
                    "policy_rule_id": qos["rule_id"],
                    "policy_reason": qos["reason"],
                    "source": "live_packet_capture",
                }
                self._recent_predictions.append(pred_entry)

                # Update live distributions
                self._class_distribution[tc["traffic_class"]] += 1
                self._congestion_distribution[cf["predicted_congestion_class"]] += 1
                self._priority_distribution[qos["final_priority"]] += 1

        except Exception as e:
            logger.error("Inference execution error on flow %s: %s", flow.flow_id, e)
            with self._lock:
                self._error_count += 1
                self._last_error = str(e)

    # ── Pipeline Lifecycle Controls ──────────────────────────────────────────

    def start(self) -> Tuple[bool, str]:
        """Start the real-time processing pipeline worker thread safely."""
        with self._lock:
            if self._is_running:
                return True, "Pipeline worker already active."

            self._stop_event.clear()
            self._start_time = time.time()
            self._is_running = True

            worker = threading.Thread(
                target=self._pipeline_worker_loop,
                name="RealTimePipelineWorker",
                daemon=True,
            )
            self._worker_thread = worker
            worker.start()

        logger.info("Real-time ML processing pipeline successfully started.")
        return True, "Real-time pipeline started."

    def stop(self) -> Tuple[bool, str]:
        """Gracefully stop the pipeline worker."""
        with self._lock:
            if not self._is_running:
                return True, "Pipeline already stopped."

            self._is_running = False
            self._stop_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

        logger.info("Real-time ML processing pipeline stopped.")
        return True, "Real-time pipeline stopped."

    def clear(self) -> None:
        """Clear all in-memory buffers and counters."""
        with self._lock:
            self._recent_packets.clear()
            self._recent_flows.clear()
            self._recent_predictions.clear()
            self._recent_traces.clear()
            self._total_packets_received = 0
            self._total_packets_dropped = 0
            self._total_inferences = 0
            self._error_count = 0
            self._last_error = None
            self._class_distribution.clear()
            self._congestion_distribution.clear()
            self._priority_distribution.clear()
        self.flow_aggregator.clear()

    # ── Data Retrieval API Methods ───────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Return comprehensive pipeline health, status, queue, and throughput metrics."""
        with self._lock:
            uptime = time.time() - self._start_time if self._start_time and self._is_running else 0.0
            return {
                "is_running": self._is_running,
                "status": "RUNNING" if self._is_running else "STOPPED",
                "uptime_seconds": round(uptime, 1),
                "queue_size": self._packet_queue.qsize(),
                "total_packets_received": self._total_packets_received,
                "total_packets_dropped": self._total_packets_dropped,
                "total_inferences_performed": self._total_inferences,
                "active_flows_count": len(self.flow_aggregator.get_active_flows()),
                "buffered_flows_count": len(self._recent_flows),
                "buffered_traces_count": len(self._recent_traces),
                "error_count": self._error_count,
                "last_error": self._last_error,
                "source": "live_packet_capture",
            }

    def get_live_flows(
        self,
        limit: int = 50,
        offset: int = 0,
        device_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieve recent live aggregated flows."""
        with self._lock:
            flows = list(self._recent_flows)
            # If ring buffer is empty but active flows exist in aggregator
            if not flows:
                flows = [f.to_dict() for f in self.flow_aggregator.get_active_flows()]

            if device_id:
                flows = [f for f in flows if f.get("device_id") == device_id]

            total = len(flows)
            paginated = list(reversed(flows))[offset : offset + limit]
            return paginated, total

    def get_live_predictions(
        self,
        limit: int = 50,
        offset: int = 0,
        device_id: Optional[str] = None,
        congestion_class: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieve recent live predictions across ML models."""
        with self._lock:
            preds = list(self._recent_predictions)
            if device_id:
                preds = [p for p in preds if p.get("device_id") == device_id]
            if congestion_class:
                preds = [p for p in preds if p.get("predicted_congestion_class") == congestion_class]

            total = len(preds)
            paginated = list(reversed(preds))[offset : offset + limit]
            return paginated, total

    def get_live_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        trace_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Retrieve structured 7-stage live decision traces."""
        with self._lock:
            traces = list(self._recent_traces)
            if trace_id:
                traces = [t for t in traces if t.get("trace_id") == trace_id]

            total = len(traces)
            paginated = list(reversed(traces))[offset : offset + limit]
            return paginated, total

    def get_live_summary(self) -> Dict[str, Any]:
        """Return aggregated live summary metrics for executive dashboard."""
        with self._lock:
            flows = list(self._recent_flows)
            devices = set(f.get("device_id") for f in flows if f.get("device_id"))
            total_records = len(flows)
            rates = [f.get("throughput_mbps", 0.0) for f in flows]

            avg_bw = float(np.mean(rates)) if rates else 0.0
            peak_bw = float(np.max(rates)) if rates else 0.0

            return {
                "source": "live_realtime",
                "total_records": total_records,
                "unique_devices": max(1, len(devices)),
                "avg_throughput_mbps": round(avg_bw, 2),
                "max_throughput_mbps": round(peak_bw, 2),
                "total_inferences": self._total_inferences,
                "class_distribution": dict(self._class_distribution),
                "congestion_distribution": dict(self._congestion_distribution),
                "priority_distribution": dict(self._priority_distribution),
            }


# Global singleton instance for application lifecycle
pipeline_manager = RealTimePipelineManager()
