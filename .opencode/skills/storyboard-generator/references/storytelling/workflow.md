# Workflow

This is the full 15-step pipeline that the skill should follow by default.

For each step:

- identify the goal
- produce the right deliverable
- avoid the common failure

## Step 1: Full Script Read

Goal:

- understand dramatic structure before thinking about shots

Output:

- short notes on protagonist, desire, opposition, turning points, climax, hooks, and audience-information order

Do not:

- start writing detailed lens coverage

## Step 2: Sequence Drama Map

Goal:

- split the script into playable dramatic sections

Output:

- a sequence list with each section's dramatic core and what changes by the end

Spatiotemporal rationalization (apply before splitting):

- drama is not a 1:1 reproduction of physical spacetime — a few seconds of screen time may represent hours, days, or years of story-world time
- only at plot points (turns, confrontations, reveals) does screen time return to real-time equivalence with the story world
- identify time-flow nodes: compressed (screen ≪ story, for fast exposition), real-time (screen ≈ story, for plot points), expanded (screen > story, for放大 key instants)
- use the change points between time-flow types as scene-division boundaries, decomposing the plot into story nodes
- each node records: name, time-flow type, story-world duration, estimated screen duration, key information to convey

Do not:

- split into shots yet
- treat every scene boundary as real-time — most transitions compress time

## Step 3: Per-Sequence Camera Strategy

Goal:

- assign each sequence a visual breathing pattern

Output:

- for each sequence: opening size, pressure direction, information pattern, reaction ownership bias, climax placement

Do not:

- design isolated cool shots without sequence logic

## Step 4: Scene Dramatic Core + Shot Flow

Goal:

- decide how each scene will progress before writing exact shots

Output:

- scene core
- audience position
- reaction owner
- continuity anchor
- first close-up timing
- scene climax duty
- shot-flow sentence

Do not:

- confuse scene analysis with a playable visual plan

## Step 5: Rough-Thumbnails Pass 1

Goal:

- run the whole piece in the roughest usable form

Output:

- scene-by-scene thumbnail task sheet with approximate panel counts and core visual problems to solve

Do not:

- polish too early

## Step 5.5: Dialogue Timing Gate

Goal:

- verify that every line of scripted dialogue physically fits within its assigned panel hold time

Output:

- per-panel timing calculation embedded in the rough thumbnail sheet
- per-scene timing validation summary table
- resolution record (compressed dialogue, adjusted emotion, extended panel, or split panel)

Procedure:

Agent computes timing for each panel **autonomously** — no script needed. The LLM judges the emotion from context and calculates the speech time using the model below.

1. For each panel with dialogue, judge the delivery emotion from scene context.
2. Look up the rate:

   | Emotion | Multiplier | Rate | Typical context |
   |---------|-----------|------|-----------------|
   | 悲恸 | 0.50x | 2.0 chars/s | sobbing, choking, crying |
   | 犹豫 | 0.60x | 2.4 chars/s | stuttering, hesitating |
   | 沉重 | 0.75x | 3.0 chars/s | trembling, suppressed grief |
   | 低语 | 0.85x | 3.4 chars/s | whispering, intimate |
   | 正常 | 1.00x | 4.0 chars/s | dialogue, narrative voiceover |
   | 急促 | 1.15x | 4.6 chars/s | urgent, panicked, rushed |
   | 激昂 | 1.25x | 5.0 chars/s | rallying, projected, firm |
   | 爆发 | 1.30x | 5.2 chars/s | shouting, roaring, explosive |

3. Compute `speech_time = chinese_char_count ÷ rate + punctuation_pauses + emotion_pauses`.
   - Punctuation pauses: comma 0.3s, period/exclamation/question 0.5s, ellipsis 0.8s, em-dash 0.5s.
   - Emotion pauses: per-clause additional pause based on emotion (e.g. 悲恸 +0.5s/clause, 犹豫 +0.4s/clause, 沉重 +0.3s, 低语 +0.2s, 爆发 +0.1s).
4. Write the calculation directly into the panel's `台词时长` field.
5. Compare against the panel's `hold` time.
6. For cross-panel continuous speech (e.g. voiceover playing over a montage), sum the hold time across all those panels and compare against the total speech time.

Pass criteria:

- Single panel: speech_time ≤ hold (dialogue must fit within the panel — no overflow tolerance)
- Cross-panel continuous: total_speech_time ≤ total_panel_hold

When a panel fails:

1. **First try**: compress the dialogue — keep the core information, drop modifiers and repetitions. (Most fixes live here.)
2. **Second try**: adjust the emotion — check if the emotion annotation is too heavy (e.g. 悲恸 0.50x drastically slows speech). A lighter emotion may be more accurate.
3. **Third try**: extend the panel's hold time — but verify that the new hold does not break the scene's rhythm.
4. **Last resort**: split the panel into two — only when neither compression, emotion adjustment, nor extension can resolve the conflict.

Record the result for each scene:

```
## Scene X Timing Validation

| Panel | 台词字数 | 情绪 | 语速 | 朗读 | 停顿 | 需时 | hold | 填充率 | 状态 |
|-------|---------|------|------|------|------|------|------|--------|------|
| 6-1   | 31      | 悲恸 | 2.0  | 15.5s| 2.6s | 18.1s| 1.5s | 1207%  | ⚠️   |
| 6-2   | 24      | 沉重 | 3.0  | 8.0s | 1.1s | 9.1s | 2.0s | 455%   | ⚠️   |
| ...   | ...     | ...  | ...  | ...  | ...  | ...  | ...  | ...    | ...  |

跨面板连续：台词 27.2s / 面板 3.5s → ⚠️ 超时 23.7s
→ 解决方案：压缩台词至 12 字，调整情绪为沉重，匹配面板 3.5s
```

Do not:

- skip this step because the scene "feels right" — speech time and visual time are different clocks
- leave unresolved overflow panels for Phase B — fix them in Phase A before writing the JSON
- delegate timing calculation to a script — the LLM is better at judging emotion from context than keyword matching

## Step 6: Animatic-Thinking Review

Goal:

- test the piece as a timed sequence

Output:

- rhythm notes
- information-order risks
- false-climax risks
- missing hold points

Do not:

- judge by single stills alone

## Step 7: Big Structure Revision

Goal:

- fix the whole before fixing the details

Output:

- what to cut
- what to protect
- what to delay
- what to strengthen

Do not:

- keep polishing scenes that sit on a broken structure

## Step 8: Single-Scene Shot-Language Refinement

Goal:

- lock the lens grammar of each scene

Output:

- how the scene opens
- when it goes close
- where it holds
- where it cuts hard
- what motivates transitions

Do not:

- rely on explanatory prose instead of shot logic

## Step 9: Rough-Thumbnails Pass 2

Goal:

- rerun the boards after the language fix

Output:

- revised panel list with clearer focal points, hold notes, and cut motivations

Do not:

- assume the first rough pass already solved progression

## Step 10: Key Panels

Goal:

- lock the few images that carry the real dramatic weight

Output:

- key-panel sheet for the most valuable beats

Do not:

- spread equal detail everywhere

## Step 11: Coarse Animatic Plan

Goal:

- test where the sequence must breathe and where it must cut fast

Output:

- hold list
- fast-cut list
- sound-first list
- danger list for false busyness

Do not:

- treat timing as an afterthought

## Step 12: Shot-By-Shot Boards For Key Scenes

Goal:

- get the most important scenes to an executable board state

Output:

- numbered shots with image, action, sound, and cut duty

Do not:

- turn them into essays

## Step 13: Full Rough Board Package

Goal:

- assemble a full-project board skeleton

Output:

- shot count
- board order
- phase rhythm
- review criteria

Do not:

- call it done if the story still reads weakly

## Step 14: Clean-Pass Rules

Goal:

- protect the solved storytelling from being ruined during polish

Output:

- what clean is allowed to improve
- what clean must not change
- priority shots
- final checklist

Do not:

- use clean pass to redesign the sequence

## Step 15: Final Delivery

Goal:

- collapse the validated workflow into one primary deliverable

Output:

- clean-integrated final storyboard master document
- short delivery note explaining what is final and what remains reference-only

Do not:

- leave the user with only process files and no single source of truth
- treat rough-board summaries as the final outward-facing deliverable
- ship a final master that is still missing per-shot production fields

## Resume Rule

If the user already has materials from a later stage:

1. identify the highest stable completed step
2. preserve it if it still works
3. resume from the next broken or missing step

## Compression Rule

If the user only asks for a smaller slice:

- do not force all 15 steps into the response
- still think through the earlier steps internally
- expose only the necessary deliverables
