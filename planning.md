# Provenance Guard — Planning

## 1. Detection Signals

I'm using two signals:

1. **LLM Detector (Groq, llama-3.3-70b-versatile)** — sends the text to the model
   with a classification prompt asking whether it reads as human or AI-generated.
   Output: a score between 0-1 (probability AI-generated). Captures semantic and
   stylistic coherence holistically — it "feels out" fluency patterns rather than
   measuring anything concrete.

2. **Stylometric heuristics (pure Python)** — computes sentence length variance
   and type-token ratio (vocabulary diversity) on the raw text. Output: a score
   between 0-1, normalized from the raw metrics. AI text tends to be more uniform;
   human writing has more variance.

These are independent: one is semantic (the model's holistic read), the other
structural (measurable statistics). That's what makes combining them more
informative than either alone.

**Combination:** weighted average.
`confidence_raw = (0.6 * llm_score) + (0.4 * stylometry_score)`

I weighted the LLM detector higher because it reads the whole text holistically,
while stylometry only captures a narrow structural slice — it's a strong signal
but easier to fool by accident (see edge cases below).

## 2. Uncertainty Representation

`confidence` = likelihood the content is AI-generated, range 0.00–1.00.

| Range | Verdict |
|---|---|
| confidence ≥ 0.70 | High-confidence AI |
| 0.30 < confidence < 0.70 | Uncertain |
| confidence ≤ 0.30 | High-confidence human |

Important detail: for the "high-confidence human" label, I don't display the raw
`confidence` score — I display `(1 - confidence) * 100` as the "how sure are we"
percentage. Otherwise a confidence of 0.18 (very human) would show as "18%
confidence" next to a label that says "high confidence," which is contradictory.

## 3. Transparency Label Design

- **High-confidence AI** (confidence ≥ 0.70):
  > "This content is likely AI-generated (High confidence: {{confidence_percent}}%)."
- **Uncertain** (0.30 < confidence < 0.70):
  > "We are uncertain about the origin of this content (Confidence: {{confidence_percent}}%)."
- **High-confidence human** (confidence ≤ 0.30):
  > "This content is likely written by a human (High confidence: {{confidence_percent}}%)."

For AI/Uncertain, `confidence_percent` = `confidence * 100`.
For Human, `confidence_percent` = `(1 - confidence) * 100`.

## 4. Appeals Workflow

Any creator can appeal a classification on their own content via `POST /appeal`.
They submit `content_id` and `creator_reasoning` (free text — why they believe
the classification is wrong). On receipt, the system:
- Sets the content's status to `"under_review"`
- Logs the appeal in the audit log alongside the original decision
- Returns a confirmation to the creator

No automated re-classification — a human reviewer would look at the appeal queue
(out of scope for this project, but the data structure supports it).

## 5. Anticipated Edge Cases

1. **Non-native English writers with formal, structured prose.** My stylometry
   signal rewards variance; a writer who learned English formally and writes
   uniformly (low sentence-length variance, careful punctuation) could score
   high on the AI side despite being 100% human. This is the appeal scenario I'm
   designing for.
2. **Short-form content with repetition for stylistic effect** (e.g., a poem
   using deliberate repetition, or a blog post with a short, punchy sentence
   style). Low variance here doesn't mean AI — it means a stylistic choice. My
   stylometry signal alone would misread this; the LLM signal is there partly
   to catch what stylometry misses.

## Architecture
Creator
|
v
POST /submit (text, creator_id)
|
+--> Signal 1: LLM Detector (Groq) -----> llm_score (0-1)
|
+--> Signal 2: Stylometry ---------------> stylometry_score (0-1)
|
v
Confidence Engine (weighted average) -------> confidence (0-1)
|
v
Transparency Label (threshold lookup) ------> label text
|
+--> Audit Log (every decision, structured)
|
v
Response JSON (content_id, attribution, confidence, label)
Creator
|
v
POST /appeal (content_id, creator_reasoning)
|
+--> Update content status -> "under_review"
|
+--> Audit Log (appeal entry, linked to original decision)
|
v
Confirmation response
A submission flows through both signals in parallel, gets combined into one
confidence score, mapped to a label, and logged — all before the response goes
back to the creator. An appeal doesn't re-run detection; it just flags the
content for human review and records the creator's reasoning next to the
original decision so a reviewer has full context.

## AI Tool Plan

- **M3 (submission endpoint + Signal 1):** I'll give Cursor the Detection
  Signals section above + the architecture diagram, and ask for (1) a Flask
  app skeleton with a `POST /submit` stub, and (2) the `llm_detector(text)`
  function. I'll verify by calling `llm_detector()` directly with 2-3 test
  strings before wiring it into the route.
- **M4 (Signal 2 + confidence scoring):** I'll give Cursor the Detection
  Signals + Uncertainty Representation sections + diagram, and ask for (1) the
  `stylometry_signal(text)` function and (2) the `compute_confidence()` function
  combining both per my weighted formula. I'll verify by checking that the
  combination math matches my stated weights (0.6 / 0.4) exactly, and testing
  against the spec's 4 example inputs to confirm scores spread across the range.
- **M5 (production layer):** I'll give Cursor the Transparency Label + Appeals
  Workflow sections + diagram, and ask for (1) `get_label(confidence)` and (2)
  the `POST /appeal` endpoint. I'll verify the label function reproduces all
  three exact label strings at boundary values (0.69, 0.70, 0.30, 0.31), and
  that an appeal call updates status and audit log correctly.