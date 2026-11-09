# Processing and verification

The commands below are real sprite-gen verbs. `sprite-gen` means the selected checkout's venv executable, not an arbitrary global installation. Run `import-gif --help` to confirm the version. On Windows PowerShell, use `& $sg` after assigning `$sg` to the absolute `.venv\Scripts\sprite-gen.exe` path. Quote absolute paths containing spaces.

```text
sprite-gen import-gif <source.gif> --out-dir <new-run> --state side-walk --base-image <master.png> --loop true
sprite-gen preview --run-dir <new-run>
sprite-gen compose-atlas --run-dir <new-run>
sprite-gen compose-gif --run-dir <new-run>
sprite-gen export-pngs --run-dir <new-run> --selected-only
sprite-gen export-godot --run-dir <new-run>
sprite-gen export-aseprite --run-dir <new-run>
```

Choose only the requested engine exports. `import-gif` never generates media or calls a provider. It accepts one action per run and refuses an existing output directory. Revisions use a new run, preserving earlier assets.

## Import options

| Option | Meaning |
|---|---|
| `--state side-walk` | Action/direction ID using letters, digits, underscores or hyphens |
| `--base-image <path>` | Accepted identity reference for the curation view |
| `--key none` | Default: retain decoded transparency and colours |
| `--key magenta`, `green`, `white` | Remove the same declared background from every frame |
| `--loop true`, `false` | Game playback policy; source repeat metadata remains archived |
| `--loop source` | Default: absent repeat metadata means one play, zero means infinite; finite counts require an explicit choice |
| `--fallback-duration-ms 100` | Replace only missing/zero delays, with a warning listing affected frames; requires a positive multiple of 10 |
| `--scale 0.5` | Uniform scale for the entire source canvas, at most 1; no per-frame fitting |
| `--canvas 256x256` | Fixed canvas containing the scaled source; centre horizontally and align its bottom vertically |
| `--pixel-art` | Nearest-neighbour resize for verified pixel art; otherwise use premultiplied-alpha downscaling |

Scaling retains the source movement. The transform in `gif-source.json` records scale, integer resized dimensions, output canvas and placement. It is not an inferred foot/root anchor. When an engine needs a semantic root, establish it from the accepted reference and apply the same coordinate transform; do not substitute each frame's alpha-bounds bottom. For several actions, choose the same character scale and enough common canvas room; automatic multi-action registration is outside this version.

## Files and ownership

```text
<run>/
  sprite-request.json          # states.<id>.durations_ms: working source-frame timing
  gif-source.json              # immutable import facts, original delays/repeats, transform/hash
  gif-import.report.json       # structural checks, warnings, needs-visual-review
  base-source.<ext>            # optional accepted reference
  source/animation.gif         # original bytes
  source/frame-N.png           # fully composited decoded frames before cleanup
  frames/<state>/frame-N.png   # processed frames, before curation
  frames/frames-manifest.json
  curation.json                # optional picks/order/clones/transforms/pixel edits
  qa/<state>-contact.png
  qa/<state>.gif               # source-order QA playback
  sprite-sheet-alpha.png
  manifest.json                # final playback order, durations and atlas rectangles
  curated/                    # baked selected PNG delivery
  curated/animation.json      # ordered PNG filenames, native durations and loop flag
  exports/<state>.gif          # final curated playback
  exports/aseprite.json
  exports/godot/sprite-frames.tres
  exports/godot/sprite-sheet-alpha.png
```

Native `durations_ms` is authoritative; the imported state's `fps` is a fallback/reference value, not a second timing editor. Curation selection/reordering maps durations through the source index; a clone inherits its source duration. Composition derives final durations and never edits archived source facts. Existing rows without native timing continue to use FPS.

For edited previews use `compose-gif`; `preview` intentionally displays pre-curation frames. The curation row, comparison playback and zoom editor read native durations. Row GIF download preserves them. The older comparison capture and row video export use a fixed sample rate and refuse native-timing rows rather than silently retiming them. Use PNG/atlas/GIF/Godot/Aseprite exports in this version. Do not use `compose-cycle`, row regeneration, interpolation or video loop repair as a GIF timing editor.

## Verification

Read the import report, then inspect all contact frames and watch the final row GIF. Check moving alpha on light and dark backgrounds; a numerically successful key does not establish clean hair or correct anatomy. Opaque frames and edge contacts are reported for review, never silently approved. Empty frames, static inputs, invalid formats and missing delays without an explicit fallback are refused. Finite source repeats are recorded separately because the game's `loop` boolean cannot represent an arbitrary repeat count.

The importer limits decoded/output data to 1000 frames and 64 million pixels per sequence. For larger inputs, obtain a shorter/smaller animation rather than silently dropping frames. A failed import does not publish a partially usable run.

After export, check that the final layout count equals the duration count, all durations are positive, every atlas rectangle is inside the image, and the total time/loop flag match the accepted sequence. Use `inspect-motion --source <run>/manifest.json --state <id>` for timing and duplicate-pose evidence (inspect its help first); contact/stride conclusions require declared foot evidence. In Godot the relative frame duration divided by animation speed must equal the manifest duration in seconds.

Pillow may combine identical adjacent GIF pictures into a longer hold. Compare the displayed timeline and accumulated time, not just `n_frames`. GIF delay units are 10 ms; import preserves positive source delays exactly. If manually edited timing is not representable in GIF ticks, use the PNG/engine timeline as truth and disclose preview quantization.
