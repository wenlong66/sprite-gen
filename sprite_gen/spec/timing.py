# SPDX-License-Identifier: Apache-2.0
"""Playback timing: imported durations take precedence over a row's fallback FPS."""
from __future__ import annotations

from sprite_gen.spec.layout import state_frame_total


def frame_durations(spec: dict, count: int) -> list[int]:
    durations = spec.get("durations_ms")
    if "durations_ms" not in spec:
        return [max(1, round(1000 / (float(spec.get("fps", 6)) or 6)))] * count
    if (not isinstance(durations, list) or len(durations) != count
            or any(type(value) is not int or value <= 0 for value in durations)):
        raise ValueError(f"durations_ms must contain {count} positive integer milliseconds")
    return list(durations)


def playback_durations(request: dict, state: str, ordered: list[int], curation: dict | None) -> list[int]:
    from sprite_gen.curate.curation import source_frame_index

    count = state_frame_total(request, state)
    durations = frame_durations(request["states"][state], count)
    return [durations[source_frame_index(curation, state, index, count)] for index in ordered]
