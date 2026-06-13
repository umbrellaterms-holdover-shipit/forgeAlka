"""Window computations for conversation indexing.

This module defines helpers for computing sliding windows over message
IDs within spines. A window is a contiguous sequence of message IDs
of fixed size. Windows are used for conversation traversal metrics.
"""

from __future__ import annotations

from typing import Dict, List


def compute_windows(spine: List[str], window_size: int = 3) -> List[List[str]]:
    """Compute sliding windows of message IDs."""
    windows: List[List[str]] = []
    for i in range(len(spine)):
        window = spine[max(0, i - window_size + 1) : i + 1]
        windows.append(window)
    return windows