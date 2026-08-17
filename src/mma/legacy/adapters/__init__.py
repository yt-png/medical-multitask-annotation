"""Legacy prelabel adapters: algorithm raw Mapping -> intermediate payloads (T2.3).

Not part of the V1 runtime path. Real SEG/DET/CAP algorithm calls are out of
scope. Base classes constrain future implementations; Example adapters support
legacy demos/tests only.
"""

from mma.legacy.adapters.cap import CapPrelabelAdapter, ExampleCapAdapter
from mma.legacy.adapters.context import AdapterContext, build_prelabel_item
from mma.legacy.adapters.det import DetPrelabelAdapter, ExampleDetAdapter
from mma.legacy.adapters.seg import ExampleSegAdapter, SegPrelabelAdapter

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
