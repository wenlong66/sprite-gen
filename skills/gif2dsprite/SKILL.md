---
name: gif2dsprite
description: Create game sprite animations from model-generated or supplied animated GIFs. Use when the user chooses GIF generation or asks to turn a GIF into transparent frames, a sprite atlas, Godot SpriteFrames, or Aseprite JSON. Preserve frame timing, character identity and motion; reuse sprite-gen for decoding, cleanup, curation and export. Ordinary static images and video clips use their existing workflows.
---

# GIF to 2D Sprite

One accepted character reference establishes identity. One GIF supplies one action and direction. Deterministic processing turns it into fixed-canvas frames and engine assets, retaining each frame's hold time.

## Engine and scope

Use the sprite-gen checkout specified by the user, `SPRITE_GEN_ROOT`, or the current workspace. Run its `.venv/Scripts/sprite-gen.exe` on Windows or `.venv/bin/sprite-gen` on macOS/Linux; a configured `sprite-gen` console command is also suitable. Check `import-gif --help` once. If that verb is missing, report that this skill needs the GIF-enabled engine; do not install an unrelated similarly named package or use an arbitrary global Python.

This skill owns explicit GIF requests even if a general character skill normally routes motion to video. It does not make a static image tool support animation. No API key or paid route is implied by the presence of this skill.

Read [generation.md](references/generation.md) when making a new GIF. Read [processing.md](references/processing.md) when a GIF is available. Existing GIFs skip all generation questions.

## Workflow

1. **Plan.** Use known context; ask only for missing choices that affect the result. Record the reference, identity, facing, style, action phases, intended loop or single play, output size and requested engine. Keep one action and direction per source GIF. Begin with the requested action rather than generating an unsolicited whole set.
2. **Establish the reference.** Reuse the user's accepted full-body still. If one is needed, use the available image-generation workflow and establish the reference before motion generation. Keep character proportions and accessories stable across all actions. Reserve room for limbs, weapons, capes and jumps.
3. **Check the generation route.** Inspect actual tool capabilities: reference input, animated file output and artifact retrieval. Use the user's named route. Do not invent a GIF flag on `image_gen`, claim a model from prompt text, or substitute MP4, repeated stills or code animation. If unavailable, leave the plan and prompt ready and explain the missing capability; supplied GIFs can still be processed.
4. **Generate or adopt.** Submit the reference plus a motion prompt once per action. Save the returned original GIF, prompt, generation parameters and actual route/model/task identifier when supplied. Resume an existing task instead of submitting it twice. Preserve accepted takes; retry only the failed action within the agreed budget. Without a retry budget, make one candidate, report the defect and propose the specific correction.
5. **Import.** Use `import-gif` into a new directory. It verifies the format and changing frames, resolves local updates/disposal/palettes, records source timing, optionally removes a fixed background, and applies one scale and canvas transform. Choose `--loop true` for a requested loop and `--loop false` for a single action. `--loop source` preserves infinite/no-repeat semantics; finite repeats require an explicit game-loop choice.
6. **Review geometry and transparency.** Read `gif-import.report.json`; inspect every frame, the contact sheet and light/dark composites. Native transparency is preserved; painted checkerboards are not alpha. Edge contact can mean clipping and needs inspection. Never fix lost source pixels by padding, scale every pose to its own bounds, pin jumping feet to the floor, or discard detached weapons/effects as small components.
7. **Review motion and rhythm.** Watch at native timing. A walk needs leg alternation and a complete gait cycle; an attack needs readable anticipation, impact and recovery. View the loop seam or the full one-shot ending. A still bobbing is not a walk. Holds can be intentional: no default interpolation, near-duplicate deletion, reversed recovery or ping-pong gait. Source-art defects require a corrected take; cleanup defects return to import with corrected parameters in a new run.
8. **Curate if needed.** Use the project's curation UI for selection, ordering, clones, transforms or pixel edits. Native hold times follow their source frames. Its speed selector changes review speed only. Export the row GIF to check edited motion; `preview` is the pre-curation contact-sheet aid. Native timing has no FPS stepper; comparison capture and WebM/MP4 retiming are outside this version.
9. **Compose and export.** Run `compose-atlas`, `compose-gif`, and `export-pngs --selected-only`. Add `export-godot` or `export-aseprite` when requested. Recompose after curation. Deliver the baked PNGs under `curated/`, not the pre-curation `frames/`. The final `manifest.json` owns engine frame order and durations.
10. **Verify and report.** Check exported frame/duration counts, positive holds, total time, runtime loop flag and atlas bounds. For a GIF re-encode, identical adjacent frames may merge; compare timed playback and total duration rather than encoded frame count alone. Report numerical checks separately from visual review. Never call an unseen animation accepted.

## Acceptance and delivery

Deliver the atlas, runtime manifest, selected transparent PNGs, native-speed GIF, contact sheet, requested engine export, original GIF and provenance. Quote actual frame count, unique pictures, total duration, canvas size and loop mode. Include every import warning and any visual issue that remains. If playback cannot be viewed, say motion remains unverified.

An import's `ok: true` means processing succeeded; `status: needs-visual-review` is deliberately not an artistic approval. GIF palette/alpha limitations cannot be recovered by converting to PNG. Keep original and derived assets separate and retain the previous accepted take.
