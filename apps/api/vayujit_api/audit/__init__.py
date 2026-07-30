"""Audit module boundary."""

from vayujit_api.audit.models import AuditEvent
from vayujit_api.audit.service import record_event

__all__ = ["AuditEvent", "record_event"]
