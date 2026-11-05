# Exploration Copilot backend work plan

Prepared for Atif and Edwin on 5 November 2026.

Build one complete workflow: a user selects a real prospect, asks about it, and receives an understandable answer linked to measurements that Ruthan can check. A prospect or lead is an area worth investigating further.

Edwin owns reading the data and producing checked measurements. Atif owns the server, the AI workflow, and reliable answers. Both work against the same saved data format so Atif can continue with synthetic data while Edwin works on the HPC.

The first synthetic-data fixes now cover citations across answers, ranking after lead selection, and exact location checks. The wider tasks below still include real-data integration, evidence validation, model reliability, and the blind test.

## How the backend works

| Step | What happens | Owner | Existing code |
|---|---|---|---|
| 1 | Read the underground survey and well measurements | Edwin | `engine/io.py`, `engine/wells.py` |
| 2 | Calculate maps and measurements for a selected interval | Edwin | `engine/attributes.py`, `engine/precompute.py` |
| 3 | Identify candidate leads and attach observations and assumptions | Edwin with Ruthan | `engine/leads.py` |
| 4 | Save a small collection of results that the app can load quickly | Edwin | `meta.json`, `wells.json`, `leads.json`, maps and section data |
| 5 | Serve those results to the existing frontend | Atif | `backend/store.py`, `backend/views.py`, `backend/app.py` |
| 6 | Choose measurement tools and ask Gemma to explain their results | Atif | `backend/tools.py`, `backend/agent.py`, `backend/llm.py` |
| 7 | Display the answer and its supporting evidence | Atif with Shane | Existing frontend API and chat modules |

An API is the agreed way the frontend asks the backend for information. Precompute means doing the heavy calculations before a user asks a question. A citation is a link from a claim to the measurement or source supporting it.

## Starting point

The existing code already provides a FastAPI server, data readers, candidate detection, an AI client, an offline answer writer, and frontend connections. The synthetic pipeline has run, API routes have been exercised, and the ten sample questions completed. Expert scoring and verification against real HPC data are separate checkpoints.

The review identified these issues to carry into implementation:

| Issue | Consequence | Task | Status |
|---|---|---|---|
| `hide_wells` is accepted but not applied | The blind test can expose the hidden outcome to the assistant | A06 with Edwin | Pending |
| Evidence IDs restart at E1 and the frontend uses one shared lookup | An earlier answer's citation can open a later answer's evidence | A02 | Answer-specific evidence implemented; wider evidence validation pending |
| Offline planning handles a selected lead before a ranking request | Asking to rank leads can return only the selected lead's explanation | A03 | Fixed and tested with synthetic data; conversation context pending |
| Coordinate lookups silently clamp to the survey edge | A nonexistent location can receive a real value under the wrong coordinates | E02 and A01 | Exact lookup and error handling tested with synthetic data; real-data alignment pending |
| A partially streamed model answer is followed by the fallback answer | Users can see two explanations joined together | A04 | Pending |
| Risk scores use fixed formulas | Displayed probabilities need an explicit assumption basis and expert review | E04 | Pending |

## First shared milestone

Choose one small area and these three questions:

1. What is the possible trapping mechanism here?
2. Which measurements support it, and what alternative explanation remains?
3. What should the geoscientist investigate next?

The milestone is ready when the selected area matches DUG Insight, the measurements are traceable, and Ruthan agrees that the answer is reasonable for the evidence available. An honest answer can state that the evidence is insufficient.

## Edwin tasks

### E01 Inspect the real inputs

Start with file headers and a small sample. Record the available volumes, survey dimensions, sample axis and units, map coordinates, coordinate scaling, missing traces, well files, available log curves, and available outcome labels. Estimate memory before loading all volumes; the current reader loads complete arrays.

With Ruthan, choose one interval and area. Confirm whether interpreted horizons, fault picks, and a usable relationship between well depth and seismic time exist. Keep unknown well outcomes as unknown.

Deliverable: an inventory and a chosen sample, kept on the HPC if they contain restricted information.

Ready when Ruthan can locate the same sample in DUG Insight and the team knows which evidence is available.

### E02 Check alignment and well placement

Check that volumes refer to the same inline, crossline, and sample coordinates before combining them. Matching array sizes alone are insufficient. Align compatible inputs explicitly or stop with a clear explanation.

Check well positions against DUG Insight. The current code averages the lower part of the deviation path as an approximate location; replace this with the position at the target interval where supported. Preserve the method and uncertainty if only an approximate position is available. Do not overlay depth logs onto a seismic time axis without a valid conversion.

Reject outside-survey or absent grid coordinates instead of silently returning an edge or adjacent cell. If nearest-cell sampling is deliberately used, report the actual sampled location and distance.

Deliverable: one checked map, a section, and the associated well positions.

Ready when Ruthan checks the selected area and several well locations, and invalid-location checks return a clear unavailable result.

### E03 Produce traceable measurements

Calculate only the maps needed for the first workflow. Process the relevant windows in manageable chunks or one volume at a time if the inventory shows that full loading is too large.

For each measurement, retain its source file, selected area or interval, unit, method, parameters, and build identifier. Use the same reviewed sand threshold in candidate detection and the derived top-sand surface. The current precompute path does not pass the selected threshold into that surface calculation.

Represent missing measurements as unavailable, never as zero. Keep measured values, derived values, expert interpretations, and assumptions distinguishable.

Deliverable: a small saved result collection compatible with the existing backend.

Ready when Ruthan can reproduce selected values or explain a documented difference from the corresponding DUG Insight view.

### E04 Review leads and risk assessments

Begin with one reviewed lead. Treat automatic shape, fault, and closure labels as candidate interpretations requiring review. Record which geometry is measured and which is inferred. A sand body or nearby discontinuity alone should not become a confirmed trap or sealing fault.

Have Ruthan review the rules and numerical factors in `engine/leads.py`. Show provisional screening scores as provisional. Only present a number as a probability of success when its assumptions and calibration are defensible. Keep unknown factors visible rather than filling them with apparently measured certainty.

Use the selected reservoir interval for well summaries when it can be established. Whole-well statistics must be labelled as such. Discovery-versus-dry averages are descriptive evidence; they are not, by themselves, a calibrated prediction model.

Deliverable: one reviewed lead, supporting measurements, alternatives, and explicit assumptions.

Ready when every displayed interpretation or score has an understandable basis that Ruthan accepts.

### E05 Make builds repeatable

Build into a new output directory, validate the result, and then select it as the active store. Guard output paths before any replacement; the current precompute function deletes an existing output directory. Preserve the previous working build until its replacement is verified.

Record the input versions, interval, thresholds, and code version. Use stable lead identifiers, or explicitly invalidate saved selections and answer caches when identifiers change between builds.

Deliverable: a repeatable build command and a result collection with a known version.

Ready when a second build from the same inputs agrees on the checked measurements and the app can identify which build it is displaying.

## Atif tasks

### A01 Stabilise the API and input checks

Keep the current routes working while adding validation. Agree any field changes with Edwin and Shane. Check unknown lead IDs, invalid coordinates, empty questions, and unsupported options. Use a clear error or unavailable response rather than returning unrelated measurements.

Add result-build information and capability flags to health or metadata responses. Advertise features such as hidden-well exclusion only when implemented and verified.

Deliverable: a predictable API that serves the synthetic store and accepts Edwin's checked store using configuration.

Ready when the existing UI loads and valid and invalid requests behave consistently.

### A02 Keep evidence attached to its answer

Give each answer an identifier and keep its evidence separate from other answers. Keep the existing `[E1]` style within each answer, with the frontend resolving it against that answer's evidence collection. Coordinate the change in `frontend/js/chat.js` with Shane.

Carry Edwin's source information through the API. Check that cited evidence exists and refers to the stated lead, measurement, unit, and comparison. Numeric matching alone cannot establish that a claim is supported.

Validate structured facts before presenting them. If text is streamed before all checks finish, mark it provisional and give the frontend a clear final accepted or rejected state. Never present a failed check as a verified answer.

Deliverable: reliable citations across chat, evidence panels, and exported summaries.

Ready when users can ask about two different leads and still open the correct evidence from the first answer.

### A03 Improve question handling

Handle explicit ranking requests before the default selected-lead explanation. Preserve the selected lead for questions that actually concern it. Handle unavailable leads and failed tools without crashing the answer writer.

Add bounded conversation context so follow-ups such as "Why?" or "What about the seal?" retain the relevant question and lead. Reset or explain context when the selection changes. Keep conversation state separate between users or sessions.

Validate the tool name and arguments before execution. Keep tool use limited and return a useful insufficient-evidence answer if the necessary facts are unavailable.

Deliverable: predictable answers to the three main questions, ranking, and follow-ups.

Ready when the same explicit ranking request works with and without a selected lead, and a follow-up uses the correct context.

### A04 Make model and fallback behaviour reliable

Use synthetic evidence locally and test the shared Gemma endpoint from the HPC. Confirm the model name, supported response behaviour, and timeouts. Keep the existing offline mode available for development.

If the model stops halfway, explicitly replace its unfinished answer or discard it before displaying the fallback. Do not append a template to the partial model output. Label model, offline, and cached answers accurately.

Cache only completed validated answers. Include the data build, model and prompt versions, selected lead, audience, hidden-well configuration, and relevant conversation context in the cache identity. Write cache updates safely and avoid stale results after a data rebuild.

Deliverable: a model-backed answer and clear behaviour when the model is unavailable or interrupted.

Ready when normal operation, initial failure, and failure after some output each leave one understandable final answer.

### A05 Build a small evaluation suite

Turn the reproduced issues into focused automated checks. Include ranking after selection, unknown leads, outside-survey coordinates, evidence isolation, missing measurements, model interruption, and stale-cache prevention.

Work with Ruthan and Vincent on reference answers for the three main questions and several missing-evidence cases. Run the existing evaluation harness and have Ruthan score the responses. Report completed runs separately from geological quality scores.

Deliverable: passing behaviour checks and a scored question set.

Ready when a code change can be checked against the same examples and the team can explain the remaining failures.

### A06 Implement the blind test after the core workflow

Create a request-specific evidence view that excludes the selected well's outcome, logs, outcome-derived summaries, and associated labels from every model-accessible source. This includes the planner's well list, tool outputs, analog descriptions, history, and cached responses. Keep the permitted seismic observations available.

Edwin owns rebuilding any calibration or other preparation influenced by the held-out outcome. If a derived product cannot be separated, disclose that limitation and avoid claiming an independent blind evaluation.

Store the actual outcome separately for the reveal step. Return a structured prediction or unknown result; do not infer the prediction by searching free text for words such as "gas" or "dry".

Deliverable: one demonstrably independent holdout case, with provenance for the excluded information.

Ready when inspection of model inputs and tool outputs shows no hidden outcome, and changing that outcome alone cannot change the evidence or prompts available before the reveal. A single case is a demonstration, not a general accuracy estimate.

## The shared data handoff

Keep the existing store layout for the first integration. New fields below are proposed additions to agree together, not fields already available everywhere.

| Output | Edwin supplies | Atif uses it for |
|---|---|---|
| `meta.json` | Survey and sample coordinates, units, interval, build identifier, parameters, quality flags | Labels, input validation, version checks |
| `wells.json` | Reviewed positions, outcome or unknown, interval summaries, location method | Well displays and evidence tools |
| `leads.json` | Lead geometry, measurements, reviewed interpretation, assumptions, scores with their basis | Lead details, comparisons, grounded answers |
| Maps and section data | Images and arrays with their axes and source information | Existing map and section endpoints |
| Evidence provenance | Source, unit, area or interval, method, build identifier, measured or inferred status | Citations and validation |

Atif should be able to switch from the synthetic store to Edwin's store through `COPILOT_STORE_DIR`, without changing frontend code for each dataset.

Keep the current frontend routes as the starting contract:

| Route | Purpose |
|---|---|
| `GET /api/health` | Available services and capabilities |
| `GET /api/meta` | Survey metadata |
| `GET /api/wells` | Well summaries |
| `GET /api/leads` | Lead list |
| `GET /api/leads/{lead_id}` | Selected lead details |
| `GET /api/map/{name}.png` | Map image |
| `GET /api/section.png?inline=...` | Seismic section |
| `GET /api/render/{name}.png` | Prepared volume or risk-stack image |
| `POST /api/chat` | Answer events and evidence |

Chat currently sends status, tool, evidence, token, and done events. Preserve them during the first integration. Agree any additional answer identifier, replacement, validation, or error events with Shane before implementation.

## Suggested work sessions

These sessions are a proposed order of work, not an official event timetable. Advance when each checkpoint is satisfied.

| Session | Atif | Edwin | Shared checkpoint |
|---|---|---|---|
| 1 | Start A01 and reproduce the known failures with synthetic data | Complete E01 with Ruthan | One selected area and an agreed data handoff |
| 2 | Complete A02 and fix ranking in A03 | Complete E02 and start E03 | Correct map and well placement; citations remain correct across answers |
| 3 | Finish core follow-ups and test Gemma for A04 | Complete E03 and review one lead for E04 | First real-data answer checked by Ruthan |
| 4 | Finish failure handling and A05 | Complete E05 and correct any quality issues | Repeatable build and a scored set of answers |
| 5 if time allows | Implement A06 | Prepare independent calibration and reveal data for A06 | Honest blind-test demonstration |
| Final integration | Test the app with Shane and rehearse with Vincent | Verify the displayed data and provenance with Ruthan | One complete demo with known limitations |

## First meeting checklist

- [ ] Ruthan selects one area and interval and explains what the available evidence can establish.
- [ ] Edwin records the available files, units, positions, and missing information.
- [ ] Atif and Edwin agree the minimum saved fields needed for that example.
- [ ] Atif and Shane agree how each answer will retain its own evidence references.
- [ ] Atif starts fixes using the synthetic store while Edwin checks real data on the HPC.
- [ ] Vincent and Ruthan write expected answers for the three main questions.
- [ ] The team schedules the first review of one real-data answer.

## Definition of ready for the demo

- [ ] The selected real-data area and wells match DUG Insight.
- [ ] Relevant measurements have source information and consistent units.
- [ ] Hypotheses and provisional scores are distinguished from measurements.
- [ ] The three main questions produce answers Ruthan can defend.
- [ ] Earlier citations stay correct after later questions.
- [ ] Ranking works after selecting a lead, and invalid locations are rejected.
- [ ] Model outages and interrupted streams leave one clearly labelled final response.
- [ ] Cached answers match the current data and evidence restrictions.
- [ ] The example can be rebuilt without losing the previous working store.
- [ ] Real and derived challenge data stay on the HPC; laptop development uses synthetic data.
- [ ] The blind test is shown only if outcome exclusion has been verified.

The first delivery is one checked area with three useful, traceable answers. Expand to more areas and similarity features after that workflow is reliable.
