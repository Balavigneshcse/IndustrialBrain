# Eval report: after-phase2 (2026-10-13)

Server: `http://127.0.0.1:8010`

| Metric | Result |
|---|---|
| Correct source anywhere in top-5 citations (answerable) | 9/9 |
| Correct source as the FIRST citation (answerable) | 8/9 |
| Benchmark answers containing the required facts | 8/10 |
| Correct refusals (Q10 + honesty probes) | 2/3 |
| False refusals on answerable questions | 0 |
| Endpoint checks (Asset 360, RCA, Analytics, unknown asset) | 4/4 |
| Median latency | 516 ms |

## Questions

| ID | Top-5 | Top-1 | Answer | Mode | Conf. | Missing / note | Answer (first 140 chars) |
|---|---|---|---|---|---|---|---|
| Q1 | ✅ | ✅ | ✅ | extractive | 0.94 |  | Based on the indexed maintenance records, observed failure modes include: bearing wear, high vibration, lubrication contamination, misalignm |
| Q2 | ✅ | ✅ | ✅ | extractive | 0.94 |  | Observed failure patterns include: bearing wear, high vibration, lubrication contamination, misalignment, overheating, pressure loss, trip.  |
| Q3 | ✅ | ✅ | ✅ | extractive | 0.75 |  | Relevant measurements include: 16 bar, 2950 rpm, 6.0 mm/s, 90 C. Primary evidence: SYNTHETIC DEMONSTRATION DATA - NOT A REAL OEM MANUAL OEM  |
| Q4 | ✅ | ✅ | ✅ | extractive | 0.94 |  | Observed failure patterns include: bearing wear, high vibration, lubrication contamination, misalignment, overheating, pressure loss. Record |
| Q5 | ✅ | ✅ | ✅ | extractive | 0.94 |  | Observed failure patterns include: bearing wear, lubrication contamination, misalignment, seal leakage. Relevant measurements include: 15 ba |
| Q6 | ✅ | ✅ | ✅ | extractive | 0.94 |  | SYNTHETIC DEMONSTRATION DATA - NOT A REAL SAFETY PROCEDURE Safety SOP: Rotating Equipment Maintenance Before opening Pump P-101 or any rotat |
| Q7 | ✅ | ✅ | ✅ | extractive | 0.73 |  | Observed failure patterns include: bearing wear, lubrication contamination, misalignment, seal leakage. Relevant measurements include: 6.0 m |
| Q8 | ✅ | ❌ | ✅ | extractive | 0.94 |  | Observed failure patterns include: bearing wear, high vibration, lubrication contamination, pressure loss, trip. Recorded maintenance action |
| Q9 | ✅ | ✅ | ❌ | extractive | 0.94 | no relation | Based on the indexed maintenance records, observed failure modes include: motor trip. Key corrective actions: calibrated, cleaned, tested. |
| Q10 | n/a | n/a | ❌ | extractive | 0.94 | (expected a refusal) | Observed failure patterns include: bearing wear, high vibration, lubrication contamination, misalignment, overheating, pressure loss, trip.  |
| P1 | n/a | n/a | ✅ | extractive | 0.0 |  | No indexed documents mention C-300, so I can't answer about it. Upload records for that equipment first. |
| P2 | n/a | n/a | ✅ | extractive | 0.0 |  | I could not find sufficient evidence in the indexed industrial documents to answer this question. Try uploading relevant documents first. |

## Endpoint checks

| Check | Result | Detail |
|---|---|---|
| Asset 360 returns evidence for P-101 | ✅ | HTTP 200, evidenceChunks=12 |
| RCA for P-101 has evidence-based causes | ✅ | HTTP 200, probableCauses=['bearing failure', 'bearing wear', 'cavitation', 'high vibration'] |
| Analytics lists failure modes | ✅ | HTTP 200, first=[{'failure': 'bearing wear', 'count': 4}] |
| Unknown asset C-300 returns 404 | ✅ | HTTP 404 |

## Corpus loaded

| File | HTTP | Status |
|---|---|---|
| compressor-c201-maintenance.txt | 202 | ready |
| operating-readings.csv | 202 | ready |
| pump-p101-inspection-report.txt | 202 | ready |
| pump-p101-maintenance-history.txt | 202 | ready |
| pump-p101-oem-manual.txt | 202 | ready |
| safety-sop.txt | 202 | ready |
