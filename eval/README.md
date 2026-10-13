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
