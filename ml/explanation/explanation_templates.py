"""Deterministic natural-language explanation templates (Phase 17).

Enforces strict explainability principles:
- Clear separation across Observation, Prediction, SHAP Attribution, Policy, and Action.
- Never asserts real-world causation (uses 'contributed to the prediction').
- Distinguishes DRY_RUN simulation from live kernel actuation.
- Generates graceful fallback statements for partial or missing stages without hallucination.
"""

from typing import Any, Dict, List, Optional


class ExplanationTemplates:
    """Provides deterministic sentence construction and paragraph synthesis."""

    @staticmethod
    def format_observations(obs: Dict[str, Any]) -> str:
        """Format observed network telemetry metrics into factual text."""
        parts = []
        if "rtt_ms" in obs and obs["rtt_ms"] is not None:
            parts.append(f"an RTT of {float(obs['rtt_ms']):.1f} ms")
        if "packet_loss_percent" in obs and obs["packet_loss_percent"] is not None:
            parts.append(f"packet loss of {float(obs['packet_loss_percent']):.2f}%")
        if "throughput_mbps" in obs and obs["throughput_mbps"] is not None:
            parts.append(f"throughput of {float(obs['throughput_mbps']):.2f} Mbps")
        if "active_connections" in obs and obs["active_connections"] is not None:
            parts.append(f"{int(obs['active_connections'])} active connection(s)")
        if "total_flow_count" in obs and obs["total_flow_count"] is not None:
            parts.append(f"{int(obs['total_flow_count'])} concurrent flow(s)")

        if parts:
            if len(parts) == 1:
                return f"Observed network conditions included {parts[0]}."
            elif len(parts) == 2:
                return f"Observed network conditions included {parts[0]} and {parts[1]}."
            else:
                return f"Observed network conditions included {', '.join(parts[:-1])}, and {parts[-1]}."
        return "Network telemetry metrics were recorded for this flow."

    @staticmethod
    def format_prediction(score: Optional[float], pred_class: str) -> str:
        """Format GRU congestion forecast statement."""
        if score is not None:
            return (
                f"The GRU congestion model predicted a congestion score of {score:.4f}, "
                f"corresponding to {pred_class} congestion."
            )
        return (
            f"The GRU congestion model did not output a time-series forecast for this sample, "
            f"defaulting to {pred_class} congestion status."
        )

    @staticmethod
    def format_shap_contributions(contributions: List[Dict[str, Any]]) -> str:
        """Format SHAP feature contributions without asserting causality."""
        if not contributions:
            return "Detailed SHAP feature attributions were not available for this prediction."

        phrases = []
        for c in contributions:
            name = c.get("feature", c.get("name", "unknown_feature"))
            val = c.get("value")
            shap_val = c.get("shap_value", 0.0)
            direction = c.get("direction", "contributed to")

            val_str = f" ({val})" if val is not None else ""
            if direction == "increased":
                verb = "increased"
            elif direction == "decreased":
                verb = "decreased"
            else:
                verb = "had a neutral effect on"

            phrases.append(f"{name}{val_str} {verb} the predicted congestion score (SHAP: {shap_val:+.4f})")

        joined = "; ".join(phrases)
        return (
            f"The primary model contributions were: {joined}. "
            f"These contributions reflect mathematical attribution toward the GRU model's score, "
            f"not real-world causation."
        )

    @staticmethod
    def format_classification(traffic_class: str, reason: str = "") -> str:
        """Format traffic classification statement."""
        base_stmt = f"The flow was classified as {traffic_class} based on configured traffic classification rules."
        cleaned_reason = reason.strip() if reason and str(reason).strip().lower() != "nan" else ""
        if cleaned_reason:
            return f"{base_stmt} ({cleaned_reason})"
        return base_stmt

    @staticmethod
    def format_user_profile(cluster_id: Optional[int], profile_label: str = "") -> str:
        """Format contextual user behavior profile statement."""
        if cluster_id is not None:
            label_str = f" ('{profile_label}')" if profile_label else ""
            return f"The device was grouped into behavior profile cluster {cluster_id}{label_str}."
        return ""

    @staticmethod
    def format_policy(
        rule_id: str,
        final_priority: str,
        base_priority: str = "NORMAL",
        policy_reason: str = "",
    ) -> str:
        """Format QoS Policy Engine decision statement."""
        rule_str = f"applied rule {rule_id} and " if rule_id else ""
        stmt = f"The QoS policy engine {rule_str}assigned {final_priority} priority."
        if policy_reason and policy_reason.strip():
            stmt += f" Policy rationale: {policy_reason.strip()}"
        return stmt

    @staticmethod
    def format_network_control(
        action: str,
        target_class: str,
        status: str,
        interface: str = "",
    ) -> str:
        """Format network traffic control action outcome."""
        iface_str = f" on interface {interface}" if interface else ""
        cls_str = f" (HTB class {target_class})" if target_class else ""

        if status == "DRY_RUN":
            return (
                f"The traffic control action {action}{cls_str}{iface_str} was simulated in dry-run mode "
                f"and was not applied to the live network."
            )
        elif status == "SUCCESS":
            return (
                f"The controller successfully applied the {action} traffic control action{cls_str}{iface_str}."
            )
        elif status == "FAILED":
            return (
                f"The requested traffic control action {action}{cls_str}{iface_str} failed "
                f"and was not applied."
            )
        elif status == "SKIPPED":
            return (
                f"The traffic control action was skipped{iface_str}."
            )
        return f"Traffic control action '{action}' reported status '{status}'."

    @classmethod
    def assemble_full_explanation(
        cls,
        trace_id: str,
        device_id: str,
        flow_id: str,
        observations: Dict[str, Any],
        pred_score: Optional[float],
        pred_class: str,
        shap_contributions: List[Dict[str, Any]],
        traffic_class: str,
        classification_reason: str,
        policy_rule_id: str,
        final_priority: str,
        base_priority: str,
        policy_reason: str,
        cluster_id: Optional[int],
        profile_label: str,
        control_action: str,
        control_target_class: str,
        control_status: str,
        control_interface: str,
    ) -> str:
        """Synthesize a coherent, multi-paragraph natural-language explanation."""
        paragraphs = []

        # 1. Observation
        obs_text = cls.format_observations(observations)
        header = f"For device {device_id}, flow {flow_id}, {obs_text[0].lower() + obs_text[1:]}"
        paragraphs.append(header)

        # 2. Prediction & SHAP
        pred_text = cls.format_prediction(pred_score, pred_class)
        shap_text = cls.format_shap_contributions(shap_contributions)
        paragraphs.append(f"{pred_text} {shap_text}")

        # 3. Traffic Classification & User Profile
        class_text = cls.format_classification(traffic_class, classification_reason)
        prof_text = cls.format_user_profile(cluster_id, profile_label)
        if prof_text:
            paragraphs.append(f"{class_text} {prof_text}")
        else:
            paragraphs.append(class_text)

        # 4. Policy Decision
        policy_text = cls.format_policy(policy_rule_id, final_priority, base_priority, policy_reason)
        paragraphs.append(policy_text)

        # 5. Network Control
        ctrl_text = cls.format_network_control(
            control_action, control_target_class, control_status, control_interface
        )
        paragraphs.append(ctrl_text)

        return "\n\n".join(paragraphs)
