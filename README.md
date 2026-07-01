# Provenance Guard

Multi-signal AI content attribution backend with confidence scoring and appeals. A backend system that classifies submitted text as AI-generated or human-written,
communicates uncertainty honestly, and lets creators appeal contested classifications.

## Architecture Overview

A submission flows through two independent detection signals in parallel, gets
combined into a single confidence score, mapped to a plain-language label, and
logged — all before the response returns to the creator.

```
POST /submit (text, creator_id)
   |
   +--> Signal 1: LLM Detector (Groq) -----> llm_score (0-1)
   +--> Signal 2: Stylometry --------------> stylometry_score (0-1)
   |
   v
compute_confidence() (weighted average) --> confidence (0-1)
   |
   v
get_label() (threshold lookup) ----------> label text
   |
   +--> Audit Log (structured JSON entry)
   |
   v
Response JSON (content_id, attribution, confidence, label, status)


POST /appeal (content_id, creator_reasoning)
   |
   +--> Update original log entry's status -> "under_review"
   +--> Append new "appeal" entry to audit log
   |
   v
Confirmation response
```

## Detection Signals

**Signal 1 — LLM Detector (Groq, `llama-3.3-70b-versatile`).** Sends the text to
the model with a classification prompt and parses a probability in [0,1] from
its response. Captures semantic and stylistic coherence holistically — it reads
the whole text the way a person would, rather than measuring anything concrete.
**Blind spot:** it's a black box — it can't tell you *which* feature of the text
drove its answer, and it can misjudge unusually formal human writing or
carefully-edited AI text.

**Signal 2 — Stylometric heuristics (pure Python, no external libraries).**
Combines two structural metrics:
- *Sentence-length rhythm*, measured as coefficient of variation (stdev / mean
  of words-per-sentence) rather than raw variance — this avoids penalizing
  naturally longer or shorter sentences. If fewer than 2 measurable sentences
  exist (no punctuation), the score falls back to vocabulary diversity alone
  rather than inventing a variance of 0.
- *Type-token ratio (TTR)* — unique words ÷ total words, a measure of vocabulary
  diversity.

Both are inverted so that uniform, repetitive structure scores *higher* on the
AI scale, matching the LLM detector's direction. **Blind spot:** this signal is
measurably less reliable on short texts (2-3 sentences) — there isn't enough
data to detect a rhythm, and TTR is sensitive to text length in general.

**Combination:** `confidence = (0.6 × llm_score) + (0.4 × stylometry_score)`.
The LLM detector is weighted higher because it reads holistically; stylometry
captures a narrower structural slice. These weights are a documented design
choice from `planning.md`, not empirically tuned on labeled data — this is
stated honestly rather than implied to be data-driven.

## Confidence Scoring

Confidence is a float in [0,1] representing likelihood the content is
AI-generated. Thresholds: `≥0.70` → likely AI, `≤0.30` → likely human,
otherwise uncertain.

**Two example submissions showing meaningfully different scores:**

| Text | llm_score | stylometry_score | confidence | attribution |
|---|---|---|---|---|
| "Artificial intelligence represents a transformative paradigm shift..." | 0.8 | — | **0.80** | likely_ai |
| "ok so i finally tried that new ramen place downtown and honestly underwhelming" | 0.2 | 0.0 | **0.12** | likely_human |

**How I validated the scores are meaningful:** I ran the spec's four
recommended test inputs (clearly AI, clearly human, borderline formal-human,
lightly-edited AI) and manually inspected both signal scores whenever a result
didn't match my intuition — see Known Limitations below for what I found.

## Transparency Label

| Variant | Threshold | Exact text |
|---|---|---|
| High-confidence AI | confidence ≥ 0.70 | `"This content is likely AI-generated (High confidence: {pct}%)."` |
| Uncertain | 0.30 < confidence < 0.70 | `"We are uncertain about the origin of this content (Confidence: {pct}%)."` |
| High-confidence human | confidence ≤ 0.30 | `"This content is likely written by a human (High confidence: {pct}%)."` |

For the AI and Uncertain variants, `pct = round(confidence * 100)`. For the
human variant, `pct = round((1 - confidence) * 100)` — this inversion matters:
a confidence of 0.12 means the system is 88% sure the text is human, so the
label correctly reads "High confidence: 88%," not "12%," which would
contradict the word "High confidence" right next to it. Verified at exact
boundary values (0.69, 0.70, 0.30, 0.31, 0.18, 0.87) before wiring into the API.

## Appeals Workflow

Any creator can appeal via `POST /appeal` with `content_id` and
`creator_reasoning`. On receipt, the system updates the original log entry's
`status` to `"under_review"` **and** appends a separate `"appeal"` entry to the
audit log containing the creator's reasoning and a timestamp — so both the
original decision and the appeal are visible side by side, and neither
overwrites the other. Returns 404 if the `content_id` doesn't exist. No
automated re-classification.

## Rate Limiting

`/submit` and `/appeal` are both limited to **10 requests/minute and 100/day
per IP**. Reasoning: a real creator submitting their own work rarely sends more
than a few pieces per session — 10/minute gives comfortable headroom without
enabling abuse. 100/day caps total exposure to the Groq API, since every
submission triggers a real (costed) LLM call.

**Evidence — 12 rapid requests to `/submit`:**
```
200 200 200 200 200 200 200 200 200 200 429 429
```
First 10 succeeded, the last 2 were rejected — confirming the limit triggers
correctly.

## Audit Log

Structured JSON file (`audit_log.json`). Each classification entry includes:
`content_id`, `creator_id`, `timestamp` (ISO 8601 UTC), `attribution`,
`confidence`, `llm_score`, `stylometry_score`, `status`. Appeal entries include
`content_id`, `event_type: "appeal"`, `creator_reasoning`, `timestamp`,
`status`. Example entry:

```json
{
  "content_id": "cffc3cec-034f-4062-90c7-304aac3c9b90",
  "creator_id": "user-123",
  "timestamp": "2026-07-01T01:58:27.273539+00:00",
  "attribution": "likely_human",
  "confidence": 0.12,
  "llm_score": 0.2,
  "stylometry_score": 0.0,
  "status": "classified"
}
```

## Known Limitations

**Signal disagreement on short, "obviously AI" text.** When I tested the
spec's own "clearly AI-generated" example paragraph, the LLM detector was
confident (0.8) but the stylometry signal disagreed (0.268, leaning human),
producing a combined confidence of 0.587 — landing in "Uncertain" instead of
"likely AI." I traced this to the stylometry signal's known weakness with
short texts (2-3 sentences give it too little data to detect a rhythm). Rather
than tune the weights to fix this one example, I documented it: the system is
being honestly uncertain, not broken, and forcing it to agree with intuition
on two anecdotal examples would be overfitting rather than genuine
calibration.

## Spec Reflection

The spec's suggestion to build the audit log starting in Milestone 3 helped —
having `log_submission()` in place before adding the second signal made it
trivial to extend the log with `stylometry_score` in Milestone 4 without
restructuring anything.

Where I diverged: the spec's Milestone 3 hints at building the audit log
alongside the very first signal; I initially left `storage.py` empty through
part of M3 to focus on getting the LLM signal correct first, and added logging
right after. This meant one early commit briefly showed `0 insertions` because
the file hadn't been populated yet when I ran `git add` — a good reminder that
git only tracks what's actually saved to disk, not what an AI tool displayed
in chat.

## AI Usage

**Instance 1 — Stylometry signal, first draft had a real bug.** I asked Cursor
to implement `stylometry_signal()` using raw sentence-length variance and TTR.
The first version returned counterintuitive results: a punctuation-less human
text scored 0.5 (should read as human, not neutral), and a clearly-AI text
scored 0.06 (should read as AI-leaning, not human). I diagnosed it by hand:
raw variance saturated the normalization cap almost instantly, and forcing a
variance of 0 for single-sentence text got inverted into "certainly AI." I
directed Cursor to switch to coefficient of variation (normalizes for natural
sentence length) and to fall back to TTR-only when fewer than 2 sentences are
measurable. I verified the fix by hand-calculating expected outputs before
accepting the new code.

**Instance 2 — Label percentage inversion.** I asked Cursor to generate
`get_label()` mapping confidence to label text. I specified upfront (from my
own `planning.md` design) that the human-confidence label needed
`(1 - confidence) * 100`, not the raw confidence, to avoid a label saying
"high confidence" next to a low percentage. Cursor implemented this correctly
on the first pass because the spec section I provided already contained the
exact formula — I verified it by testing all label boundaries (0.69, 0.70,
0.30, 0.31, 0.18, 0.87) directly against expected output before wiring it into
the API.

## Tech Stack

Python 3.13, Flask, Groq API (`llama-3.3-70b-versatile`), Flask-Limiter,
JSON-file audit log.

## Video Walkthrough
https://www.loom.com/share/9fe83ea50f9d45f6a81f558ad55a65d0
