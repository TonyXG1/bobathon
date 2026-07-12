"""
Contracts package - Pydantic models and JSON schemas.

This package defines the two core contracts:
- Requirement: Output of Part 1 (extraction), input of Part 2 (assessment)
- Finding: Output of Part 2 (assessment), input of Parts 3 & 4 (alerting, dashboard)
"""

from contracts.models import (
    Alert,
    ChangeType,
    Channel,
    Finding,
    ProductCategory,
    RegulationFamily,
    Requirement,
    Severity,
    Substance,
)

__all__ = [
    "Alert",
    "Finding",
    "Requirement",
    "ChangeType",
    "Severity",
    "Channel",
    "ProductCategory",
    "Substance",
    "RegulationFamily",
]
