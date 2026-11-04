# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from conftest import run_script
from sprite_gen.compose.export_godot import run as export_godot

ROOT = Path(__file__).resolve().parents[2]


def test_cli_exports_portable_godot_spriteframes(tmp_path: Path) -> None:
    run = tmp_path / "run"
    run.mkdir()
    image = Image.new("RGBA", (32, 16), "red")
    image.paste("blue", (16, 0, 32, 16))
    image.save(run / "atlas.png")
    a = {"x": 0, "y": 0, "w": 16, "h": 16}
    b = {"x": 16, "y": 0, "w": 16, "h": 16}
    name = 'attack"\\待机'
    manifest = {
        "game_input": "atlas.png",
        "frame_layout": {"sheetWidth": 32, "sheetHeight": 16, "rows": {"idle": [a, b, a], name: [b]}},
        "animation": {"rows": {
            "idle": {"fps": 8, "durations_ms": [125, 250, 375], "loop": True},
            name: {"fps": 12, "durations_ms": [40], "loop": False},
        }},
    }
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    result = subprocess.run(
        [sys.executable, "-m", "sprite_gen.cli", "export-godot", "--run-dir", str(run)],
        cwd=ROOT, capture_output=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is True
    bundle = shutil.copytree(run / "exports" / "godot", tmp_path / "project" / "characters" / "hero")
    text = (bundle / "sprite-frames.tres").read_text(encoding="utf-8")
    assert text.startswith('[gd_resource type="SpriteFrames" load_steps=4 format=3]')
    assert 'path="sprite-sheet-alpha.png"' in text
    assert (bundle / "sprite-sheet-alpha.png").read_bytes() == before["atlas.png"]
    assert text.count('[sub_resource type="AtlasTexture"') == 2
    assert "region = Rect2(16, 0, 16, 16)" in text
    # Read the documented animation dictionaries, replacing Godot's resource references with IDs.
    animations = text.split("animations = ", 1)[1]
    animations = re.sub(r'SubResource\("([^"\n]+)"\)', r'"\1"', animations).replace('&"', '"')
    idle, attack = json.loads(animations)
    assert idle == {
        "name": "idle", "speed": 8.0, "loop": True,
        "frames": [
            {"duration": 1.0, "texture": "AtlasTexture_0"},
            {"duration": 2.0, "texture": "AtlasTexture_1"},
            {"duration": 3.0, "texture": "AtlasTexture_0"},
        ],
    }
    assert attack == {
        "name": name, "speed": 12.0, "loop": False,
        "frames": [{"duration": 0.48, "texture": "AtlasTexture_1"}],
    }
    assert all((run / filename).read_bytes() == content for filename, content in before.items())


def test_composed_run_exports_all_curated_states(fixture_run_dir: Path) -> None:
    for script in ("extract_sprite_row_frames.py", "compose_sprite_atlas.py"):
        result = run_script(script, "--run-dir", str(fixture_run_dir))
        assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((fixture_run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert export_godot(fixture_run_dir) == 0
    output = fixture_run_dir / "exports" / "godot"
    text = (output / "sprite-frames.tres").read_text(encoding="utf-8")
    assert '"name": &"idle"' in text and '"name": &"walk"' in text
    assert text.count('"duration":') == sum(len(row) for row in manifest["frame_layout"]["rows"].values())
    assert (output / "sprite-sheet-alpha.png").read_bytes() == (fixture_run_dir / manifest["game_input"]).read_bytes()


@pytest.mark.parametrize("invalid", [
    "rows", "duration-count", "zero-duration", "fractional-duration", "empty-frames",
    "fps", "loop", "rectangle", "dimensions", "outside-image", "missing-image",
])
def test_invalid_manifest_keeps_existing_export(tmp_path: Path, invalid: str) -> None:
    Image.new("RGBA", (16, 16), "red").save(tmp_path / "atlas.png")
    row = {"fps": 8, "durations_ms": [125], "loop": True}
    rect = {"x": 0, "y": 0, "w": 16, "h": 16}
    layout = {"sheetWidth": 16, "sheetHeight": 16, "rows": {"idle": [rect]}}
    manifest = {"game_input": "atlas.png", "animation": {"rows": {"idle": row}}, "frame_layout": layout}
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert export_godot(tmp_path) == 0
    output = tmp_path / "exports" / "godot"
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    if invalid == "rows":
        layout["rows"] = {"walk": [rect]}
    elif invalid == "duration-count":
        row["durations_ms"] = [125, 250]
    elif invalid == "zero-duration":
        row["durations_ms"] = [0]
    elif invalid == "fractional-duration":
        row["durations_ms"] = [1.5]
    elif invalid == "empty-frames":
        layout["rows"]["idle"] = []
        row["durations_ms"] = []
    elif invalid == "fps":
        row["fps"] = 0
    elif invalid == "loop":
        row["loop"] = "false"
    elif invalid == "rectangle":
        rect["x"] = 1
    elif invalid == "dimensions":
        layout["sheetWidth"] = 32
    elif invalid == "outside-image":
        manifest["game_input"] = "../atlas.png"
    elif invalid == "missing-image":
        manifest["game_input"] = "missing.png"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert export_godot(tmp_path) == 1
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before


def test_missing_durations_use_manifest_fps() -> None:
    from sprite_gen.compose.export_godot import spriteframes_resource

    text = spriteframes_resource({
        "game_input": "atlas.png",
        "frame_layout": {"sheetWidth": 16, "sheetHeight": 16,
                         "rows": {"idle": [{"x": 0, "y": 0, "w": 16, "h": 16}]}},
        "animation": {"rows": {"idle": {"fps": 8}}},
    })
    assert '"duration": 1.0' in text and '"speed": 8.0' in text and '"loop": true' in text
