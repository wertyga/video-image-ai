---
name: minimax-prompting
description: End-to-end workflow for writing scripts, reference image prompts (Flux), and MiniMax H3 video prompts for realistic AI live-action videos.
---

# 🎬 MiniMax AI Video Creation Workflow

A modular, production-tested guide for generating realistic live-action AI videos using **Flux** (for starting reference frames) and **MiniMax H3** (for multimodal video generation and lip-sync).

## 1. Core Agent Interaction Rules (MUST FOLLOW)

- **Step-by-Step Execution:** Execute strictly one scene/task at a time. Never rush ahead.
- **No Unapproved Execution:** Do not write files or video prompts without explicit user confirmation. Discuss and align on concepts, locations, and outfits first.
- **No Premature Video Prompting:** NEVER write video prompts before reference images are generated, placed in `AI/Images/{scene}/`, and visually inspected. Prompts must match the actual generated assets.
- **No Assumptions / Minimal Fluff:** Answer concisely. If requirements are unclear, ask directly instead of guessing.
- **Character Consistency Confirmation:** At the very start of any project, ask:
  > *"Do you want to keep the exact same character identity across all scenes, or do you want random/different characters for each scene?"*

---

## 2. The 5-Step Production Workflow

Follow this sequence for every scene:

```
[1. Concept & Scene Planning] ➡️ [2. Draft Image Prompts] ➡️ [3. Generate Reference Images] ➡️ [4. Review Generated Assets] ➡️ [5. Write MiniMax Video Prompts]
```

1. **Concept & Scene Planning:** Decide location, wardrobe, camera style (Selfie vs. Third-Person Candid), and spoken dialogue.
2. **Draft Image Prompts:** Create image prompts (With Reference + Standalone) enforcing deep depth-of-field and raw realism.
3. **Generate Reference Images:** Generate images using Flux.
4. **Review Assets:** Check real generated poses, framing, lighting, and expressions before touching video prompts.
5. **Write Matched MiniMax Prompts:** Write video prompts tailored 1:1 to the actual image framing, audio duration, and lip-sync speech.

---

## 📸 3. Image Prompting Rules (Flux / Starting Frames)

### A. The "No Phone in Frame" Rule for Selfies (CRITICAL)
* **Never write:** *"holding phone extended in front of her"*, *"holding smartphone"*, or *"holding camera"*.
* **Why:** AI will physically place a floating or distorted smartphone into the subject's hands.
* **Correct Syntax:** Use *"Raw handheld smartphone selfie of [Subject]... She looks directly into the front-facing camera lens..."* This sets the front-camera perspective without adding a phone prop.

### B. Smartphone Optics & Sharp Backgrounds
* **Enforce:** `deep depth-of-field with subject and background both kept in sharp focus`, `crisp background detail`, `no artificial portrait mode blur`.
* **Avoid:** Artificial background bokeh or cinematic lens jargon (e.g. avoid "85mm f/1.2", "heavy bokeh"). Real smartphone wide lenses keep both subject and environment clear.

### C. Raw Natural Aesthetics
* **Enforce:** `raw handheld smartphone photo aesthetic`, `visible skin texture with visible pores`, `natural skin grain`, `no digital airbrushing`, `true-to-life color science`.
* **No Negative Phrasing:** Never use "no blur", "no freckles". State desired features positively (e.g., "clear skin with authentic micro-texture").

### D. Consistent Character Architecture
If using a recurring character across scenes, lock their physical attributes verbatim in every prompt:
* **Hair:** Length, cut, part, and color (e.g., *shoulder-length wavy brown hair with subtle golden highlights and middle part*).
* **Face & Skin:** Facial bone structure, eye color, skin undertone, natural brow shape, minimal natural makeup.
* **Wardrobe Continuity:** Plan outfits in pairs of 2 scenes (e.g., 2 scenes in loungewear, 2 scenes in workout clothes, 2 in casual streetwear) for realistic continuity.

---

## 🎥 4. MiniMax H3 Video Prompting Rules

MiniMax H3 is a multimodal video model that requires precise syntax for motion, speech, and composition retention.

### A. The "NO Shot-Framing Words" Rule (CRITICAL GOTCHA)
* **DO NOT** use shot framing words like `medium shot`, `close-up`, `tight close-up`, `wide shot`, or `medium-close` in the `summary`, `detailed_description`, or `[Shot X]` lines.
* **Why:** MiniMax treats framing words as zoom/re-crop commands, which distorts or crops your carefully generated starting image (`<Picture 1>`).
* **Correct Syntax:**
  * Standard: `a portrait of <Subject 1> as in <Picture 1>`
  * Selfie: `a selfie portrait of <Subject 1> as in <Picture 1>`
  * Environment: `a portrait of <Subject 1> standing in the kitchen as in <Picture 1>`

### B. The Mandatory 6-Section Structure
Every MiniMax H3 prompt MUST follow these 6 exact headers in order:

```text
subject_definitions:
<Subject 1> is the [character description from <Picture 1> including hair, outfit, accessories, and initial pose].
<Subject 2> is the [environment/background description from <Picture 1>].
<Audio 1> is the spoken voiceover audio track from [filename.mp3].

summary:
[reference generation] A [X]-second live-action video featuring <Subject 1> at <Subject 2>, speaking directly into the camera lens, synchronized with <Audio 1>.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - facial features, hair, outfit, and pose retained from <Picture 1>.
<Subject 2> (appears in [Shot 1]): fully_preserved - background setting, furniture, and lighting retained from <Picture 1>.
<Audio 1> (appears in [Shot 1]): fully_preserved - vocal delivery, tone, and lip-sync precisely synchronized to the speech.

detailed_description:
Live-action, raw handheld smartphone selfie aesthetic under [lighting conditions]. Natural skin texture and pores with no airbrushing. Deep depth-of-field keeping subject and background in sharp focus. Subtle handheld micro-drift.
[Shot 1] At 00:00.000, a selfie portrait of <Subject 1> as in <Picture 1>. She maintains direct eye contact with the camera lens with [expression], her mouth moving in precise synchronization with <Audio 1> to deliver: <d>[English] [Spoken dialogue line here] </d> until 00:[XX].000.

overall_soundscape:
[Subtle ambient room tone/background sound] beneath the clear voice from <Audio 1>.

non_diegetic_music:
N/A
```

### C. Dialogue & Audio Sync Formatting
* **Dialogue Tags:** Wrap spoken dialogue in `<d>[Language] ... </d>` tags.
* **Audio Reference:** Declare `<Audio 1>` in `subject_definitions` and `retention_analysis` to enforce accurate lip-synchronization with your voiceover track.
* **Timestamps:** Every shot line must start with `At 00:00.000` and specify the end timestamp matching audio length (e.g., `until 00:05.000`).

### D. Safe Motions vs. Problematic Motions
* **Supported & Stable:** Direct eye contact with lens, natural talking/lip-sync, subtle smiles, nodding, head tilts, subtle body sway, gentle handheld float.
* **Avoid:** Sudden 180-degree head turns, rapid spinning, wildly waving hands in front of face, or complex multi-limb movements that cause AI hallucination or limb merging.

---

## ⏱️ 5. Typical Timing Guidelines

* **Flash Cuts / Punchy Words:** 1.0s – 2.0s
* **Short Phrases (2–5 words):** 2.5s – 4.0s
* **Standard Sentences:** 4.0s – 6.0s
* **Long Multi-phrase Sentences:** 6.0s – 8.0s

---

## 📦 6. Dual-Format Standard Output

For every completed scene, always provide both:
1. **Unified Video Prompt:** Full multi-shot continuous scene render covering all dialogue lines in one timeline.
2. **Single-Shot Video Prompts:** Modular individual prompts (Shot 1, Shot 2, etc.) mapped directly 1:1 to each specific generated image file (`1.png`, `2.png`, etc.) for maximum control and stability.


---

## 7. Notes for this project (AdUltAi) — added on top of the original skill

The original skill above is by Midnight Lab (free download from their Gumroad). These notes adapt it to this repo:

* **Starting frames are made with Qwen Image 2.1, not Flux.** Use `scripts/generate.py` (see README and `docs/characters.md`). Reference syntax is `<image1>`, `<image2>` with `--image`, not `@image1`. "Preserve recognizable facial features" style phrasing makes Qwen paste the face 1:1 — describe new light/angle/expression instead, as in `docs/characters.md`.
* **Our H3 workflow (`workflows/h3_nsfw_server*.json`, `scripts/generate_video.py`) is the `fl2va` first/last-frame model.** It has no audio input, so `<Audio 1>` templates (#3, #5 and section 4.B as written) do not apply; speech is generated by the model from `<d>[English] ... </d>` tags — use template #4 as the base.
* **First-frame line:** the Nexus workflow's guide recommends starting I2V prompts with `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.` The `[reference generation]` tag in this skill comes from the reference-to-video mode. Which works better with `fl2va` is not verified yet — compare both on the server.
* **NSFW LoRA** (`minimax_h3_nsfw_unlocked_v2`, strength 0.5 by default): the author's trigger words are `nude`, `topless`, `naked`, `disrobing`, `slipping off robe`, `caressing`, `intimate kissing`. Put them in `detailed_description` shot lines.
* **Only fictional characters or consenting adults** as `<Picture 1>` — never photos of real people without consent.
* Images in this repo live in `characters/` and `output/`, not `AI/Images/{scene}/`.
