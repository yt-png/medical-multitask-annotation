"""Prelabel adapters: algorithm raw Mapping → unified intermediate payloads (T2.3).

Real SEG/DET/CAP algorithm calls are out of scope. Use Base classes to constrain
future implementations and Example adapters to validate the current pipeline.
"""

from mma.adapters.cap import CapPrelabelAdapter, ExampleCapAdapter
from mma.adapters.context import AdapterContext, build_prelabel_item
from mma.adapters.det import DetPrelabelAdapter, ExampleDetAdapter
from mma.adapters.seg import ExampleSegAdapter, SegPrelabelAdapter

__all__ = [
    "AdapterContext",
    "CapPrelabelAdapter",
    "DetPrelabelAdapter",
    "ExampleCapAdapter",
    "ExampleDetAdapter",
    "ExampleSegAdapter",
    "SegPrelabelAdapter",
    "build_prelabel_item",
]
