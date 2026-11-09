# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import re
import subprocess
import sys

from PIL import Image
import pytest

from sprite_gen.compose import compose_atlas, compose_gif, export_aseprite, export_godot, export_pngs
from sprite_gen.curate.curation import stamp_curation, write_curation_atomic
from sprite_gen.frames.import_gif import decode, run
from sprite_gen.frames import import_gif
from sprite_gen.frames.extract import heal_run, HEAL_KEPT_STALE
from sprite_gen.qa import preview
from sprite_gen.spec.runio import load_request
from sprite_gen.serve.serve_curation import build_run_state
from sprite_gen.util.gif_utils import gif_report


def make_gif(path, *, loop=None, durations=(80, 160, 40), disposal=2):
    frames = []
    for index in range(3):
        frame = Image.new("RGBA", (32, 32))
        frame.paste((240, 40 + index * 50, 30, 255), (4 + index * 4, 8, 12 + index * 4, 24))
        frames.append(frame)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=list(durations),
                   disposal=disposal, **({"loop": loop} if loop is not None else {}))
    return frames


@pytest.mark.parametrize("disposal", [2, 3])
def test_decoder_composites_transparent_local_rectangles_and_palettes(tmp_path, disposal):
    path = tmp_path / "input.gif"
    expected = make_gif(path, disposal=disposal)
    frames, info = decode(path)
    assert [frame.tobytes() for frame in frames] == [frame.tobytes() for frame in expected]
    assert info["durations_ms"] == [80, 160, 40]
    assert info["loop_count"] is None
    assert info["total_duration_ms"] == 280


def test_decoder_composites_retained_canvas(tmp_path):
    path = tmp_path / "retained.gif"
    frames = [Image.new("RGB", (32, 32), "white")]
    for color, x in (("red", 4), ("blue", 16)):
        frame = frames[-1].copy()
        frame.paste(color, (x, 8, x + 8, 24))
        frames.append(frame)
    frames[0].save(path, save_all=True, append_images=frames[1:], disposal=1, duration=80, optimize=True)
    decoded, _info = decode(path)
    assert [frame.convert("RGB").tobytes() for frame in decoded] == [frame.tobytes() for frame in frames]


def test_cli_import_preview_and_engine_exports_preserve_native_timing(tmp_path):
    path, output = tmp_path / "attack.gif", tmp_path / "run"
    expected = make_gif(path)
    original = path.read_bytes()
    proc = subprocess.run([sys.executable, "-m", "sprite_gen.cli", "import-gif", str(path),
                           "--out-dir", str(output), "--state", "attack"], capture_output=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["status"] == "needs-visual-review"
    assert path.read_bytes() == original
    assert (output / "source/animation.gif").read_bytes() == original
    request = load_request(output)
    assert request["states"]["attack"]["durations_ms"] == [80, 160, 40]
    assert request["states"]["attack"]["loop"] is False
    assert build_run_state(output)["states"][0]["durationsMs"] == [80, 160, 40]
    assert heal_run(output)[HEAL_KEPT_STALE] == []
    for index, frame in enumerate(expected):
        with Image.open(output / f"frames/attack/frame-{index}.png") as actual:
            assert actual.tobytes() == frame.tobytes()
    assert preview.run(run_dir=output) == 0
    assert compose_gif.run(run_dir=output) == 0
    for gif in (output / "qa/attack.gif", output / "exports/attack.gif"):
        report = gif_report(gif)
        assert report["delay_ticks"] == [8, 16, 4]
        assert report["loop"] is None
    assert compose_atlas.run(run_dir=output) == 0
    assert export_aseprite.run(run_dir=output) == 0
    assert export_godot.run(output) == 0
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["animation"]["rows"]["attack"]["durations_ms"] == [80, 160, 40]
    aseprite = json.loads((output / "exports/aseprite.json").read_text())
    assert [frame["duration"] for frame in aseprite["frames"]] == [80, 160, 40]
    godot = (output / "exports/godot/sprite-frames.tres").read_text()
    assert '"loop": false' in godot
    assert [float(value) for value in re.findall(r'"duration": ([\d.]+)', godot)] == [0.8, 1.6, 0.4]


def test_selected_reordered_cloned_frames_keep_their_own_durations(tmp_path):
    path, output = tmp_path / "walk.gif", tmp_path / "run"
    make_gif(path, loop=0)
    assert run(path, output, state="walk") == 0
    # Clone 3 is linked to frame 1; frame 0 is removed, and frame 2 is played first.
    write_curation_atomic(output, stamp_curation(output, {"version": 1, "kind": "sprite-gen-curation", "states": {"walk": {
        "selected": [2, 1, 3], "deleted": [0], "clones": {"3": 1},
    }}}))
    assert compose_atlas.run(run_dir=output) == 0
    assert compose_gif.run(run_dir=output) == 0
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["animation"]["rows"]["walk"]["durations_ms"] == [40, 160, 160]
    rects = manifest["frame_layout"]["rows"]["walk"]
    assert rects[1] == rects[2]
    # GIF encoders may merge identical adjacent cells; their total hold must survive.
    assert gif_report(output / "exports/walk.gif")["delay_ticks"] == [4, 32]
    assert export_pngs.run(run_dir=output, selected_only=True) == 0
    pngs = json.loads((output / "curated/animation.json").read_text())["states"]["walk"]
    assert pngs["files"] == ["frame-2.png", "frame-1.png", "frame-3.png"]
    assert pngs["durations_ms"] == [40, 160, 160]
    assert pngs["loop"] is True


@pytest.mark.parametrize("durations", [None, [80], [80, 0, 40], [80, True, 40], [80, 1.5, 40]])
def test_corrupt_native_timing_is_refused_before_export(tmp_path, durations):
    path, output = tmp_path / "source.gif", tmp_path / "run"
    make_gif(path)
    assert run(path, output) == 0
    request = load_request(output)
    request["states"]["idle"]["durations_ms"] = durations
    (output / "sprite-request.json").write_text(json.dumps(request))
    with pytest.raises(ValueError, match="durations_ms"):
        compose_atlas.run(run_dir=output)
    assert not (output / "sprite-sheet-alpha.png").exists()


def test_scaling_that_erases_the_subject_does_not_publish_partial_frames(tmp_path):
    path, output = tmp_path / "source.gif", tmp_path / "run"
    make_gif(path)
    assert run(path, output, scale=1 / 32, pixel_art=True) == 1
    assert not output.exists()


def test_fixed_scale_canvas_and_background_removal(tmp_path):
    path, output = tmp_path / "key.gif", tmp_path / "run"
    frames = []
    for x in (8, 12):
        frame = Image.new("RGB", (40, 40), (255, 0, 255))
        frame.paste((30, 70, 210), (x, 8, x + 12, 32))
        frames.append(frame)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=[80, 120], loop=0)
    assert run(path, output, key="magenta", scale=0.5, canvas=(24, 24), pixel_art=True) == 0
    bboxes = []
    for index in range(2):
        with Image.open(output / f"frames/idle/frame-{index}.png") as frame:
            assert frame.size == (24, 24)
            assert frame.getpixel((0, 0))[3] == 0
            bboxes.append(frame.getbbox())
    assert bboxes[1][0] - bboxes[0][0] == 2
    assert bboxes[0][1:] == (bboxes[1][1], bboxes[1][2] - 2, bboxes[1][3])


@pytest.mark.parametrize("fault", ["static", "not-gif", "zero-delay", "finite-loop", "crop", "state-path"])
def test_bad_import_does_not_publish_or_change_input(tmp_path, fault):
    path, output = tmp_path / "source.gif", tmp_path / "run"
    make_gif(path, durations=(80, 0, 40) if fault == "zero-delay" else (80, 160, 40),
             loop=2 if fault == "finite-loop" else None)
    if fault == "static":
        Image.new("RGB", (32, 32), "red").save(path)
    elif fault == "not-gif":
        Image.new("RGB", (32, 32), "red").save(path, format="PNG")
    original = path.read_bytes()
    kwargs = {"canvas": (8, 8)} if fault == "crop" else {"state": "../escape"} if fault == "state-path" else {}
    assert run(path, output, **kwargs) == 1
    assert not output.exists()
    assert path.read_bytes() == original


def test_explicit_delay_and_loop_overrides_are_recorded(tmp_path):
    path, output = tmp_path / "source.gif", tmp_path / "run"
    make_gif(path, durations=(80, 0, 40), loop=2)
    assert run(path, output, fallback_duration_ms=100, loop="false") == 0
    source = json.loads((output / "gif-source.json").read_text())
    assert source["loop_count"] == 2
    assert source["duration_replacements"] == [1]
    assert source["durations_ms"] == [80, 100, 40]
    assert source["original_durations_ms"] == [80, 0, 40]
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    assert run(path, output) == 1
    assert before == {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}


@pytest.mark.parametrize("failure", ["temporary", "permanent", "destination-appears", "other-permission"])
def test_publish_handles_windows_rename_denial_without_replacing_existing_data(tmp_path, monkeypatch, failure):
    source, output = tmp_path / "source.gif", tmp_path / "run"
    make_gif(source)
    original = source.read_bytes()
    rename = Path.rename
    attempts, waits = [], []

    def deny_then_rename(staging, target):
        attempts.append(staging)
        if len(attempts) == 1 or failure == "permanent":
            if failure == "destination-appears":
                output.mkdir()
                (output / "keep.txt").write_text("another writer's result")
            error = PermissionError("directory rename denied")
            error.winerror = 5 if failure != "other-permission" else 19
            raise error
        return rename(staging, target)

    monkeypatch.setattr(Path, "rename", deny_then_rename)
    monkeypatch.setattr(import_gif.time, "sleep", waits.append)
    result = run(source, output)
    assert source.read_bytes() == original
    if failure == "temporary":
        assert result == 0
        assert load_request(output)["states"]["idle"]["durations_ms"] == [80, 160, 40]
        assert len(attempts) == 2 and waits
    else:
        assert result == 1
        if failure == "destination-appears":
            assert (output / "keep.txt").read_text() == "another writer's result"
            assert not (output / "frames").exists()
        else:
            assert not output.exists()
        if failure == "other-permission":
            assert len(attempts) == 1 and waits == []
        if failure == "permanent":
            assert 1 < len(attempts) <= 5
    assert not list(tmp_path.glob(".run-gif-*"))
