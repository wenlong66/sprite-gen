# SPDX-License-Identifier: Apache-2.0
"""Import an animated GIF as complete RGBA cells with its native playback timing."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
import time

from PIL import Image

from sprite_gen.frames.cutout import cutout
from sprite_gen.spec.runio import REQUEST_FILENAME, REQUEST_KIND, refuse_overlap


def decode(path: Path, fallback_duration_ms: int | None = None) -> tuple[list[Image.Image], dict]:
    """Pillow's sequential decoder owns local rectangles, palettes and disposal."""
    if fallback_duration_ms is not None and (fallback_duration_ms <= 0 or fallback_duration_ms % 10):
        raise ValueError("--fallback-duration-ms must be a positive multiple of 10")
    frames, durations, original_durations, disposal, replaced = [], [], [], [], []
    with Image.open(path) as source:
        if source.format != "GIF":
            raise ValueError("input must be a GIF file, not just a file named .gif")
        size, loop = source.size, source.info.get("loop")
        for index in range(source.n_frames):
            # Bound decoded memory, not just the compressed input's byte size.
            if index >= 1000 or size[0] * size[1] * (index + 1) > 64_000_000:
                raise ValueError("GIF exceeds 1000 frames or 64 million decoded pixels; use a shorter/smaller clip")
            source.seek(index)
            duration = source.info.get("duration")
            original_durations.append(duration)
            if type(duration) is not int or duration <= 0:
                if fallback_duration_ms is None:
                    raise ValueError(f"frame {index} has missing/zero duration; supply --fallback-duration-ms explicitly")
                replaced.append(index)
                duration = fallback_duration_ms
            durations.append(duration)
            disposal.append(getattr(source, "disposal_method", 0))
            # Invisible palette colours are not changing poses.
            frame = Image.new("RGBA", size)
            frame.alpha_composite(source.convert("RGBA"))
            frames.append(frame)
    if len(frames) < 2:
        raise ValueError("GIF contains only one frame; an animated source is required")
    unique = len({hashlib.sha256(frame.tobytes()).digest() for frame in frames})
    if unique < 2:
        raise ValueError("GIF has no changing poses; repeated copies of a still are not animation")
    return frames, {
        "size": list(size), "frames": len(frames), "unique_frames": unique,
        "durations_ms": durations, "total_duration_ms": sum(durations),
        "original_durations_ms": original_durations,
        "loop_count": loop, "disposal": disposal, "duration_replacements": replaced,
    }


def _size(value: str) -> tuple[int, int]:
    try:
        width, height = (int(part) for part in value.lower().split("x"))
        if width <= 0 or height <= 0:
            raise ValueError
        return width, height
    except ValueError as exc:
        raise argparse.ArgumentTypeError("canvas must be positive WIDTHxHEIGHT") from exc


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path, help="new run directory; existing directories are refused")
    parser.add_argument("--state", default="idle", help="one action and direction per GIF, e.g. side-walk")
    parser.add_argument("--base-image", type=Path, help="accepted identity reference, copied into the run")
    parser.add_argument("--key", choices=("none", "magenta", "green", "white"), default="none",
                        help="preserve native transparency, or remove this fixed background from every frame")
    parser.add_argument("--loop", choices=("source", "true", "false"), default="source")
    parser.add_argument("--fallback-duration-ms", type=int, help="explicit replacement for missing/zero delays only")
    parser.add_argument("--scale", type=float, default=1.0, help="one fixed scale for all frames, greater than 0 and at most 1")
    parser.add_argument("--canvas", type=_size, help="fixed output canvas; must contain the entire scaled source")
    parser.add_argument("--pixel-art", action="store_true", help="use nearest-neighbour scaling for verified pixel art")


def run(input: Path, out_dir: Path, state: str = "idle", base_image: Path | None = None,
        key: str = "none", loop: str = "source", fallback_duration_ms: int | None = None,
        scale: float = 1.0, canvas: tuple[int, int] | None = None, pixel_art: bool = False) -> int:
    try:
        input, out_dir = Path(input).expanduser().resolve(), Path(out_dir).expanduser().resolve()
        base_image = Path(base_image).expanduser().resolve() if base_image else None
        if out_dir.exists():
            raise ValueError("--out-dir already exists; use a new directory")
        refuse_overlap({"input": input, "--base-image": base_image}, {"--out-dir": out_dir}, holds=("--out-dir",))
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", state):
            raise ValueError("--state must contain only letters, digits, underscores or hyphens")
        if not math.isfinite(scale) or not 0 < scale <= 1:
            raise ValueError("--scale must be greater than 0 and at most 1")
        frames, source = decode(input, fallback_duration_ms)
        source_loop = source["loop_count"]
        if loop == "source" and source_loop not in (None, 0):
            raise ValueError("finite GIF repeat count needs --loop true or --loop false for the game; source count is retained")
        runtime_loop = source_loop == 0 if loop == "source" else loop == "true"
        scaled = tuple(max(1, round(length * scale)) for length in frames[0].size)
        canvas = canvas or scaled
        if any(final < size for final, size in zip(canvas, scaled)):
            raise ValueError("--canvas must contain the whole scaled source; cropping could remove moving limbs")
        if canvas[0] * canvas[1] * len(frames) > 64_000_000:
            raise ValueError("output exceeds 64 million pixels; use a smaller canvas")
        offset = ((canvas[0] - scaled[0]) // 2, canvas[1] - scaled[1])
        warnings = []
        if source["duration_replacements"]:
            warnings.append(f"replaced missing/zero durations at frames {source['duration_replacements']}")
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".{out_dir.name}-gif-", dir=out_dir.parent) as temporary:
            staging = Path(temporary)
            originals = staging / "source"
            originals.mkdir()
            shutil.copyfile(input, originals / "animation.gif")
            if base_image:
                with Image.open(base_image) as base:
                    base.verify()
                base_name = f"base-source{base_image.suffix.lower() or '.png'}"
                shutil.copyfile(base_image, staging / base_name)
            files, checks = [], []
            folder = staging / "frames" / state
            folder.mkdir(parents=True)
            for index, frame in enumerate(frames):
                raw = originals / f"frame-{index}.png"
                frame.save(raw)
                path = folder / f"frame-{index}.png"
                key_report = None
                if key != "none":
                    key_report = cutout(raw, path, key=key)
                    key_report.pop("out", None)
                    with Image.open(path) as cleaned:
                        frame = cleaned.convert("RGBA")
                alpha = frame.getchannel("A")
                bbox = alpha.getbbox()
                if bbox is None:
                    raise ValueError(f"frame {index} is empty after background removal")
                edges = bbox[0] == 0 or bbox[1] == 0 or bbox[2] == frame.width or bbox[3] == frame.height
                checks.append({"frame": index, "bbox": list(bbox), "edge_contact": edges,
                               "transparent": alpha.getextrema()[0] == 0, "key": key_report})
                if scaled != frame.size:
                    if pixel_art:
                        frame = frame.resize(scaled, Image.Resampling.NEAREST)
                    else:
                        frame = frame.convert("RGBa").resize(scaled, Image.Resampling.LANCZOS).convert("RGBA")
                result = Image.new("RGBA", canvas)
                result.alpha_composite(frame, offset)
                if result.getchannel("A").getbbox() is None:
                    raise ValueError(f"frame {index} became empty after scaling; use a larger output size")
                result.save(path)
                files.append(path.relative_to(staging).as_posix())
            edge_frames = [check["frame"] for check in checks if check["edge_contact"]]
            opaque_frames = [check["frame"] for check in checks if not check["transparent"]]
            if edge_frames:
                warnings.append(f"source edge contact at frames {edge_frames}; inspect for clipping before acceptance")
            if opaque_frames:
                warnings.append(f"no transparent background at frames {opaque_frames}; use a suitable --key for sprite cutouts")
            cell = {"width": canvas[0], "height": canvas[1], "size": canvas[0], "safe_margin": 0,
                    "shape": "square" if canvas[0] == canvas[1] else "rect"}
            request = {"version": 1, "kind": REQUEST_KIND, "engine": "component-row",
                       "character": {"id": out_dir.name, "description": "imported GIF animation"}, "cell": cell,
                       "chroma_key": {"name": key},
                       "states": {state: {"frames": len(frames), "fps": 10, "loop": runtime_loop,
                                          "action": state, "durations_ms": source["durations_ms"]}}}
            if base_image:
                request["character"]["base_image"] = base_name
            manifest = {"ok": True, "engine": "component-row", "run_dir": str(out_dir), "cell": cell,
                        "rows": [{"state": state, "frames": len(frames), "method": "gif", "files": files, "ok": True}],
                        "errors": [], "warnings": warnings}
            source.update({"path": str(input), "sha256": hashlib.sha256(input.read_bytes()).hexdigest(),
                           "copy": "source/animation.gif", "state": state, "key": key,
                           "transform": {"scale": scale, "scaled_size": list(scaled), "canvas": list(canvas),
                                         "offset": list(offset), "pixel_art": pixel_art},
                           "runtime_loop": runtime_loop})
            if base_image:
                source["base"] = {"path": str(base_image), "copy": base_name,
                                  "sha256": hashlib.sha256(base_image.read_bytes()).hexdigest()}
            report = {"ok": True, "status": "needs-visual-review", "source": "gif-source.json",
                      "frames": len(frames), "unique_frames": source["unique_frames"],
                      "total_duration_ms": source["total_duration_ms"], "loop": runtime_loop,
                      "warnings": warnings, "checks": checks}
            for name, document in ((REQUEST_FILENAME, request), ("frames/frames-manifest.json", manifest),
                                   ("gif-source.json", source), ("gif-import.report.json", report)):
                (staging / name).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            # Windows can briefly deny renaming a newly written directory. Retry only
            # that observed error, without overwriting a destination or hiding a lasting failure.
            for attempt in range(5):
                if out_dir.exists():
                    raise ValueError("--out-dir appeared during import; refusing to replace it")
                try:
                    staging.rename(out_dir)
                    break
                except PermissionError as exc:
                    if getattr(exc, "winerror", None) != 5 or attempt == 4:
                        raise
                    time.sleep(0.05 * 2 ** attempt)
        print(json.dumps({"ok": True, "run_dir": str(out_dir), **report}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, SystemExit) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
