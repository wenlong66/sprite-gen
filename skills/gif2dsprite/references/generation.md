# Generating a source GIF

Use the tool's actual schema. A model or chat may support GIFs while a particular tool exposes only static output; text asking for animation does not change that contract. Check for an animated artifact and retrieve its original bytes through the tool's supported mechanism. A preview screenshot is not the source animation.

Keep a short plan beside the output with the character reference, action, direction, loop mode, requested size/duration, game display size and finish. Save a `prompt.txt` and a `generation.json` containing the actual route, returned model name if available, task ID if available, reference path/hash, requested parameters and returned artifact path. Unknown model, cost or frame rate stays unknown. Record requested values separately from inspected output values.

## Prompt template

> Animate the same [identity and accessories] shown in the attached reference. Create one [action] animation, viewed from [camera], facing [direction]. Keep the camera, character proportions, costume, weapon and lighting consistent. [Action phases.] [Loop or one-shot ending.] Keep the whole body and its moving accessories inside the canvas with room for [motion envelope]. Use [verified transparent output or a specified flat key colour]. No text, scene changes or extra characters. Deliver an animated GIF.

Only send supported size/duration/frame-count controls as API parameters. When phrased as creative requests, verify the resulting values after generation. Attach the actual reference; mentioning its filesystem path in a prompt is insufficient.

## Action-specific clauses

| Action | Motion requirement | Ending |
|---|---|---|
| Idle | Small readable breathing or secondary motion; stable feet and identity | Natural continuation into the first pose |
| Walk | In-place full gait: near-leg contact, passing, far-leg contact, passing; both feet alternate | Same phase and direction, no half-step loop |
| Attack | Anticipation, acceleration, impact, recovery; consistent weapon | Complete recovery or a deliberate final pose; single play |
| Jump | Take-off, ascent, apex, descent, landing; preserve vertical travel | Landing and settle; single play |

Use the master's actual colours to choose a key; green is inappropriate for a green character, magenta for a purple/pink design. The key should be flat and stable across frames. Native GIF transparency is a transparent palette index, not continuous alpha.

## Correcting a take

Name one observed defect and add the corresponding correction: full-body margin for clipped extremities, fixed camera for zoom, stable handedness for a changing weapon, alternating foot contacts for bobbing, or uninterrupted facing for an unintended turn. Retain the identity reference. Do not change colour, design and motion simultaneously unless those changes were requested.

If the source is structurally correct but has unwanted lead-in or trailing poses, select a valid interval in curation and inspect it as motion. Do not assume that similar endpoint pictures prove a correct gait or a seamless loop. Do not auto-fill long holds: they may be timing accents.
