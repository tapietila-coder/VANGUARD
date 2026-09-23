"""Incidents / alerting: correlates real failure signals already produced
elsewhere in this codebase (readiness, Service Control, Job Queue, the
Dispatch integration adapter) into Incident records an operator can see,
acknowledge, and track. See detector.py for the correlation rules and
store.py for persistence. No synthetic alert source, no external
paging/alerting integration — local detection and grouping only."""
