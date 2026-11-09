# SPDX-License-Identifier: Apache-2.0
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
import urllib.error
import urllib.request

from PIL import Image
import pytest

from sprite_gen.frames.import_gif import run as import_gif
from sprite_gen.serve.serve_curation import CurationHandler


def test_browser_timing_follows_selected_and_cloned_source_frames():
    store = Path(__file__).resolve().parents[2] / "sprite_gen/serve/curator/src/store.js"
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const context = vm.createContext({assert});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
vm.runInContext(`
run = {states: [{name: 'attack', fps: 10, durationsMs: [80, 160, 40]}, {name: 'legacy', fps: 8}]};
entries = {attack: {order: [2, 1, 3], sel: new Set([2, 1, 3]), clones: {3: 1}}, legacy: {clones: {}}};
const durations = playList('attack').map(i => frameDurationMs('attack', i));
assert.deepEqual(durations, [40, 160, 160]);
assert.equal(durations.reduce((a,b) => a + b, 0), 360);
assert.equal(frameDurationMs('legacy', 0), 125);
`, context);
"""
    result = subprocess.run(["node", "-e", script, str(store)], capture_output=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr


def test_native_timing_cannot_be_overwritten_by_legacy_fps_editor(tmp_path):
    source, output = tmp_path / "source.gif", tmp_path / "run"
    frames = [Image.new("RGB", (16, 16), color) for color in ("red", "blue")]
    frames[0].save(source, save_all=True, append_images=frames[1:], duration=[80, 160])
    assert import_gif(source, output) == 0
    request_file = output / "sprite-request.json"
    before = request_file.read_bytes()
    CurationHandler.run_dir = output
    CurationHandler.lang = "en"
    server = ThreadingHTTPServer(("127.0.0.1", 0), CurationHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/api/state-fps",
            data=json.dumps({"state": "idle", "fps": 24}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=5)
        assert error.value.code == 400
        assert "native GIF frame timing" in error.value.read().decode()
        assert request_file.read_bytes() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
