# Evaluation

A repeatable functional benchmark for IndusMind. It runs the real HTTP API against the synthetic corpus in `sample-data/`, so different versions can be compared on equal terms.

| File | Purpose |
|---|---|
| `benchmark.jsonl` | The 10 benchmark questions plus 2 honesty probes, each with its expected sources and required facts |
| `run_eval.py` | Harness (standard library only): asks every question, grades it, probes Asset 360 / RCA / Analytics, and writes a report |
| `serve_and_eval.ps1` | Runs the harness against a throwaway server, with a fresh `indusmind_eval` database and a scratch upload folder |
| `reports/` | One JSON + Markdown report per run, named `<date>-<label>` |

## Run it

The database container must be running (`docker compose up -d db`).

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\eval\serve_and_eval.ps1 -Label my-run
```

## Benchmark

| # | Question | Expected evidence |
|---|---|---|
| 1 | Why did Pump P-101 fail repeatedly in 2025? | Bearing wear, contaminated lubrication, misalignment, vibration, temperature |
| 2 | How many major bearing events occurred for P-101? | Three significant bearing-related events |
| 3 | Which readings exceeded OEM limits? | Vibration above 6.0 mm/s; bearing temperature above 90 C |
| 4 | What maintenance was performed on 22-Nov-2025? | Bearing and seal replacement; housing flush; test |
| 5 | What did the lubricant sample show? | Water and metallic particles |
| 6 | What safety steps apply before pump maintenance? | Permit, shutdown, LOTO, valve isolation, zero energy, PPE |
| 7 | What alert thresholds were recommended? | 6.0 mm/s and 90 C |
| 8 | What was P-101 pressure after verification? | 15 bar |
| 9 | Did C-201 cause the P-101 failure? | No evidence of a relation |
| 10 | What was the P-101 motor current? | Insufficient evidence; the system should not invent one |
| P1 | Identify risks for compressor C-300 | Refuse: C-300 is not in the corpus (from real query logs) |
| P2 | Get me the CGPA in the resume | Refuse: out-of-corpus question (from real query logs) |

## Metrics

| Metric | Meaning |
|---|---|
| Top-5 / top-1 source | The expected document appears among the citations, or as the first citation |
| Answer facts | Every group of required facts appears in the answer. This is a minimum bar, not a quality judge. |
| Correct refusals | Q10 and the probes are answered with "insufficient / no evidence" |
| False refusals | An answerable question was refused |
| Endpoint checks | Asset 360 and RCA return evidence for P-101; Analytics lists failure modes; the unknown asset C-300 returns 404 |

## Acceptance targets

- Equipment-tag extraction: at least 90% on the included corpus.
- Correct source document among the top five results: at least 85%.
- Every supported answer includes at least one citation.
- Unsupported questions explicitly report insufficient evidence.
- Local response time: under 15 seconds for the demonstration corpus.

## Results so far

| Report | First citation correct | Answer facts | Correct refusals | Endpoint checks |
|---|---|---|---|---|
| `2026-10-13-baseline-original` | 5/9 | 3/10 | 0/3 | 2/4 |
| `2026-10-13-after-phase0` | 5/9 | 3/10 | 1/3 | 4/4 |
| `2026-10-13-after-phase1` | 5/9 | 3/10 | 1/3 | 4/4 (answers identical to Phase 0) |
| `2026-10-13-after-phase2` | **8/9** | **8/10** | **2/3** | 4/4 (no false refusals) |
| `2026-10-14-after-phase3` | 8/9 | **10/10** | **3/3** | 4/4 (no false refusals; answers by Qwen3-4B) |

Phase 2 replaced hashed bag-of-words vectors with hybrid retrieval (bge-small vectors plus Postgres full text, fused, then reranked), structure-aware chunks and per-chunk entities. The remaining misses need a language model (Phase 3):
- **Q9:** the extractive template cannot phrase "no relation".
- **Q10:** recognising that a specific fact, motor current, is absent from relevant P-101 evidence.

### Reranker choice and evidence threshold (Phase 2)

Top reranker probability per question on this corpus:

| Question | MiniLM-L6 (chosen) | bge-reranker-base |
|---|---|---|
| Answerable, worded like the text (Q1, Q2, Q4–Q6, Q8, Q9) | 0.96 – 1.00 | 0.17 – 1.00 |
| Answerable, worded differently (Q3, Q7) | 0.108, 0.007 | 0.036, 0.009 |
| Q10 (motor current, not recorded) | 0.956 | 0.046 |
| P2 (CGPA, out of corpus) | 0.000 | 0.001 |
| First citation correct | 8/9 | 7/9 |
| Time for 21 pairs (CPU) | 83 ms | 604 ms |

- **Threshold:** neither reranker separates Q10 from the correctly answerable Q3 and Q7 by score. So `MIN_EVIDENCE_SCORE` is 0.005: it rejects only clearly unrelated questions and causes no false refusals.
- **Fact-level refusals** ("this fact is not in the evidence") are left to the language model in Phase 3.

### Phase 3: generation with Qwen3-4B

Answers are now written by Qwen3-4B-Instruct-2507 (Q4_K_M, Ollama, all layers on the RTX 3050). The extractive answer is the fallback when the model is offline: `serve_and_eval.ps1 -NoLlm` measures that fallback.

| Metric | Phase 2 (extractive) | Phase 3 |
|---|---|---|
| Answer facts | 8/10 | 10/10 |
| Correct refusals | 2/3 | 3/3 (Q10 "Insufficient evidence: … motor current") |
| False refusals | 0 | 0 |
| Answers with numbers not found in the sources | n/a | 0 |
| Citations to non-existent sources | n/a | 0 |
| Median / slowest answer | 516 ms / – | 2.6 s / 8.4 s, under the 15 s target |
| Evidence strength high / medium / low | – | 6 / 2 / 4 (all 4 lows are refusals or a weak retrieval match: Q7) |

**Prompt development** (`answer.v1` → `answer.v2`): the facts check alone was not enough, so the answers were read in full.
- **`answer.v1`:**
  - It concluded "misalignment was not the root cause". The sources say the opposite: misalignment was found, corrected, and "increased vibration loading".
  - It appended an "Insufficient evidence:" line to complete answers.
- **`answer.v2`** forbids conclusions the sources do not state, and notes that a corrected fault does not rule out an earlier cause.
- **The settings now used:**
  - A one-line rule reminder follows the question.
  - Temperature 0.1 with a fixed seed.
  - A trailing "Insufficient evidence:" after an answer is relabelled "Not covered by the sources:".

  Together these removed the invented conclusion and the RCA's "indicating …" interpretations, and kept answers short.
- **What remains:**
  - The first sentence of Q9 ("No, C-201 did not cause …") has no citation, so it is flagged.
  - Q3 notes a "gap" that is really a range comparison.

  These are the kinds of behaviour the Phase 5 fine-tune targets.
