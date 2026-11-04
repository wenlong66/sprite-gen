# Engine export

> Owns: Godot 4 SpriteFrames and Aseprite-compatible export for Phaser and Flame · Index: [docs/README.md](README.md)

## Godot 4

After `compose-atlas`, export a portable animation resource:

```bash
$SPRITE_GEN_ROOT/.venv/bin/sprite-gen export-godot --run-dir <run-dir>
```

This writes two files under `<run-dir>/exports/godot/`:

- `sprite-frames.tres` — native Godot 4 `SpriteFrames`, with one animation per state.
- `sprite-sheet-alpha.png` — a byte-for-byte copy of the composed atlas.

Copy the **whole folder** anywhere inside your Godot project, then assign `sprite-frames.tres` to an `AnimatedSprite2D` node's **Sprite Frames** property (or `AnimatedSprite3D`'s equivalent). Select an animation and play it. The texture path is relative to the resource, so the folder can move without editing `res://` paths. For pixel art, choose **Nearest** in the node's texture filter settings.

The resource preserves animation names, playback order, repeated frames, loop flags and per-frame millisecond durations. Shared atlas cells use the same `AtlasTexture` subresource; no images are re-encoded. Frame durations are converted to Godot's relative units with `duration_ms * fps / 1000`, preserving timing at the exported animation FPS. It reads the composed `manifest.json`, so re-run `compose-atlas` first after changing curation selections, transforms or pixel edits.

Godot 3 resource syntax, scenes and gameplay logic are outside this export. The exporter rejects invalid animation mappings, timing, out-of-bounds rectangles and missing or mismatched PNGs before publishing. Both output files use the pipeline's staged file-set writer; the source atlas and manifest are unchanged.

Format references: [Godot SpriteFrames](https://docs.godotengine.org/en/stable/classes/class_spriteframes.html) and [text resource external references](https://docs.godotengine.org/en/stable/engine_details/file_formats/tscn.html#external-resources).

## Aseprite-compatible JSON

`sprite-gen export-aseprite` describes a composed sprite-gen atlas using the JSON schema consumed by Aseprite loaders. It does not create an editable `.aseprite` source file and it does not re-encode the PNG.

Run it after `compose-atlas`:

```bash
$SPRITE_GEN_ROOT/.venv/bin/sprite-gen export-aseprite --run-dir <run-dir>
```

The default output is `<run-dir>/exports/aseprite.json`. It pairs with the existing `sprite-sheet-alpha.png` named by `manifest.json.game_input`. Because compose already applied `curation.json`, the export includes the final selected order, reused cells, transforms, pixel edits, clones, and breathe cells through the atlas rectangles it references.

## Mapping

| sprite-gen manifest | Aseprite-compatible JSON |
|---|---|
| `frame_layout.rows.<state>[i]` | `frames[]` rectangle in playback order |
| `animation.rows.<state>.durations_ms[i]` | frame `duration` in milliseconds |
| state name and global frame range | `meta.frameTags[]` |
| `game_input` | `meta.image` |
| `frame_layout.sheetWidth` / `sheetHeight` | `meta.size` |

Repeated playback instances keep repeated rectangles under distinct numeric frame keys. This preserves sprite-gen's shared-cell representation while presenting the sequential frame keys expected by engine loaders.

## Phaser

Phaser accepts Aseprite JSON in array or hash form and creates animations from `meta.frameTags`. The default `json-array` output uses stringified global frame indices, the tag ranges, and each frame's own duration.

```javascript
this.load.aseprite('hero', 'sprite-sheet-alpha.png', 'aseprite.json');
this.anims.createFromAseprite('hero');
this.add.sprite(100, 100, 'hero').play('idle');
```

Phaser's official API documents `load.aseprite` and `createFromAseprite`; its implementation looks up each tagged frame by the stringified numeric index and reads each frame's duration. Sources: [Phaser AnimationManager](https://docs.phaser.io/api-documentation/4.0.0/class/animations-animationmanager), [Phaser source](https://github.com/phaserjs/phaser/blob/master/src/animations/AnimationManager.js).

## Flutter and Flame

Flame's `SpriteAnimation.fromAsepriteData` expects `frames` to be a map and builds one animation from every value in that map. It does not read `meta.frameTags`. Export one hash file per state:

```bash
$SPRITE_GEN_ROOT/.venv/bin/sprite-gen export-aseprite --run-dir <run-dir> --format json-hash --split-states
```

This writes `exports/aseprite/idle.json`, `walk.json`, and so on. Every file uses local indices beginning at `0`, points to the same atlas PNG, and preserves millisecond frame durations. The relevant behavior is visible in Flame's official [`SpriteAnimation.fromAsepriteData` source](https://github.com/flame-engine/flame/blob/main/packages/flame/lib/src/sprite_animation.dart).

## Aseprite export limits

- The exporter is structurally tested against the fields the loaders consume, but the repository does not run a browser Phaser app or Flutter runtime in CI.
- `loop` remains in `manifest.json`. Aseprite frame tags carry direction and range but no sprite-gen loop policy, and Flame's Aseprite factory constructs its default looping animation without reading tags.
- Engine exports run through the CLI after compose; the curation webview has no engine-export download button.
- The exporter refuses malformed row mappings and output paths outside the run directory. Split-state files are staged as a complete directory and then published together.

## Related

- [docs/README.md](README.md) — documentation index
