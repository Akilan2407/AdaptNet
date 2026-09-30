"""Natural-Language Explanation Module — Phase 17."""

from ml.explanation.config import (
    DEFAULT_EXPLANATIONS_CSV,
    DEFAULT_EXPLANATIONS_JSONL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_TXT,
    DEFAULT_SUMMARY_JSON,
    STATUS_FAILED,
    STATUS_PARTIAL,
    STATUS_SKIPPED,
    STATUS_SUCCESS,
    TOP_FEATURES,
)
from ml.explanation.explanation_builder import ExplanationBuilder, ExplanationRecord
from ml.explanation.explanation_generator import ExplanationGenerator
from ml.explanation.explanation_templates import ExplanationTemplates
from ml.explanation.explanation_validator import ExplanationValidator
from ml.explanation.report_generator import ReportGenerator

__all__ = [
    "ExplanationGenerator",
    "ExplanationBuilder",
    "ExplanationRecord",
    "ExplanationTemplates",
    "ExplanationValidator",
    "ReportGenerator",
    "TOP_FEATURES",
    "STATUS_SUCCESS",
    "STATUS_PARTIAL",
    "STATUS_SKIPPED",
    "STATUS_FAILED",
]
