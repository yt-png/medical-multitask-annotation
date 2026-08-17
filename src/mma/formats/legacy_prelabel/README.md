"""Legacy prelabel format (historical reference).

``legacy_prelabel`` holds the unified SEG/DET/CAP prelabel intermediate types
(``PrelabelDocument`` / ``PrelabelItem`` / payloads) and sample JSON files.

It is **not** the V1 runtime schema. V1 uses ``task_schema`` and
``annotation_schema`` (re-exported from ``mma.common.models``). CLI /
``ls-import`` / merge do not depend on this package for first-round flow;
some rework / converter helpers may still import it until a later phase.
"""
