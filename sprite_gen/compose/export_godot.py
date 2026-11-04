# SPDX-License-Identifier: Apache-2.0
"""Export a composed atlas as a portable Godot 4 SpriteFrames resource and PNG."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image

from sprite_gen.compose.export_aseprite import aseprite_json
from sprite_gen.spec.runio import acquire_run_dir_lock, atomic_write_set, read_guard
from sprite_gen.util.console import utf8_streams

ATLAS_NAME = "sprite-sheet-alpha.png"
RESOURCE_NAME = "sprite-frames.tres"


def spriteframes_resource(manifest: dict[str, Any]) -> str:
    """Map the composed playback order to Godot 4's text resource format."""
    data = aseprite_json(manifest)
    width, height = data["meta"]["size"]["w"], data["meta"]["size"]["h"]
    if any(type(size) is not int or size <= 0 for size in (width, height)):
        raise ValueError("atlas dimensions must be positive integers")
    regions: dict[tuple[int, ...], str] = {}
    animations = []
    for tag in data["meta"]["frameTags"]:
        state = tag["name"]
        row = manifest["animation"]["rows"][state]
        fps = float(row.get("fps", 6))
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError(f"{state}: fps must be positive and finite")
        loop = row.get("loop", True)
        if not isinstance(loop, bool):
            raise ValueError(f"{state}: loop must be a boolean")
        durations = row.get("durations_ms")
        if durations is not None and (not isinstance(durations, list) or not durations
                or any(type(d) is not int or d <= 0 for d in durations)):
            raise ValueError(f"{state}: durations_ms must contain positive integer milliseconds")
        if tag["to"] < tag["from"]:
            raise ValueError(f"{state}: animation must contain at least one frame")
        frames = []
        for frame in data["frames"][tag["from"]:tag["to"] + 1]:
            rect = tuple(frame["frame"][key] for key in ("x", "y", "w", "h"))
            if any(type(value) is not int for value in rect):
                raise ValueError(f"{state}: atlas rectangles must contain integers")
            x, y, w, h = rect
            if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
                raise ValueError(f"{state}: frame rectangle is outside the atlas")
            ident = regions.setdefault(rect, f"AtlasTexture_{len(regions)}")
            # Godot stores relative durations: seconds = duration / animation FPS.
            duration = frame["duration"] * fps / 1000.0
            if not math.isfinite(duration) or duration <= 0:
                raise ValueError(f"{state}: frame duration must be positive and finite")
            frames.append(f'{{"duration": {duration!r}, "texture": SubResource("{ident}")}}')
        animations.append(
            '{"frames": [' + ", ".join(frames) + '], "loop": ' + str(loop).lower()
            + ', "name": &' + json.dumps(state, ensure_ascii=False) + f', "speed": {fps!r}' + "}"
        )
    if not animations:
        raise ValueError("manifest must contain at least one animation")
    lines = [
        f'[gd_resource type="SpriteFrames" load_steps={len(regions) + 2} format=3]', "",
        f'[ext_resource type="Texture2D" path="{ATLAS_NAME}" id="1_atlas"]', "",
    ]
    for (x, y, w, h), ident in regions.items():
        lines.extend([
            f'[sub_resource type="AtlasTexture" id="{ident}"]',
            'atlas = ExtResource("1_atlas")', f"region = Rect2({x}, {y}, {w}, {h})",
            "filter_clip = true", "",
        ])
    lines.extend(["[resource]", "animations = [" + ",\n".join(animations) + "]", ""])
    return "\n".join(lines)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-dir", required=True, type=Path)


def run(run_dir: Path) -> int:
    run_dir = Path(run_dir).resolve()
    try:
        acquire_run_dir_lock(run_dir, "export-godot")
        with read_guard(run_dir):
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            text = spriteframes_resource(manifest)
            image_path = (run_dir / manifest["game_input"]).resolve()
            if not image_path.is_relative_to(run_dir):
                raise ValueError("game_input must stay inside the run directory")
            with Image.open(image_path) as image:
                layout = manifest["frame_layout"]
                if image.format != "PNG" or image.size != (layout["sheetWidth"], layout["sheetHeight"]):
                    raise ValueError("atlas PNG dimensions do not match manifest.json")
                image.verify()
            output = (run_dir / "exports" / "godot").resolve()
            if not output.is_relative_to(run_dir / "exports"):
                raise ValueError("Godot output must stay under the run's exports/ directory")
            output.mkdir(parents=True, exist_ok=True)
            atomic_write_set({output / ATLAS_NAME: image_path.read_bytes(), output / RESOURCE_NAME: text})
            report = {
                "ok": True, "output": str(output / RESOURCE_NAME), "image": str(output / ATLAS_NAME),
                "states": list(manifest["animation"]["rows"]),
            }
    except (OSError, KeyError, TypeError, ValueError, OverflowError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    return run(**vars(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
