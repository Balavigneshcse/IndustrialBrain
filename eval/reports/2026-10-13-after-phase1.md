# Eval report: after-phase1 (2026-10-13)

Server: `http://127.0.0.1:8010`

| Metric | Result |
|---|---|
| Correct source anywhere in top-5 citations (answerable) | 9/9 |
| Correct source as the FIRST citation (answerable) | 5/9 |
| Benchmark answers containing the required facts | 3/10 |
| Correct refusals (Q10 + honesty probes) | 1/3 |
| False refusals on answerable questions | 0 |
| Endpoint checks (Asset 360, RCA, Analytics, unknown asset) | 4/4 |
| Median latency | 17 ms |

## Questions

| ID | Top-5 | Top-1 | Answer | Mode | Conf. | Missing / note | Answer (first 140 chars) |
|---|---|---|---|---|---|---|---|
| Q1 | ✅ | ✅ | ✅ | extractive | 0.76 |  | Based on the indexed maintenance records, observed failure modes include: bearing wear, high vibration, lubrication contamination, misalignm |
| Q2 | ✅ | ✅ | ❌ | extractive | 0.76 | three | Observed failure patterns include: bearing wear, high vibration, lubrication contamination, misalignment. Recorded maintenance actions inclu |
| Q3 | ✅ | ✅ | ✅ | extractive | 0.74 |  | Observed failure patterns include: bearing failure, cavitation, high vibration, misalignment. Relevant measurements include: 16 bar, 6.0 mm/ |
| Q4 | ✅ | ❌ | ❌ | extractive | 0.75 | bearing, seal, flush | Observed failure patterns include: motor trip. Recorded maintenance actions include: calibrated, cleaned, tested. Relevant measurements incl |
| Q5 | ✅ | ❌ | ❌ | extractive | 0.76 | water, metallic | Observed failure patterns include: bearing wear, high vibration, lubrication contamination, misalignment. Recorded maintenance actions inclu |
| Q6 | ✅ | ✅ | ✅ | extractive | 0.79 |  | SYNTHETIC DEMONSTRATION DATA - NOT A REAL SAFETY PROCEDURE Safety SOP: Rotating Equipment Maintenance Before opening Pump P-101 or any rotat |
| Q7 | ✅ | ❌ | ❌ | extractive | 0.75 | 6.0 mm/s, 90 c | date \| asset_tag \| vibration_mm_s \| bearing_temperature_c \| discharge_pressure_bar \| status 2025-01-12 \| P-101 \| 6.8 \| 92 \| 14.5 \| |
| Q8 | ✅ | ❌ | ❌ | extractive | 0.78 | 15 bar | Observed failure patterns include: motor trip. Recorded maintenance actions include: calibrated, cleaned, tested. Relevant measurements incl |
| Q9 | ✅ | ✅ | ❌ | extractive | 0.78 | no relation | Based on the indexed maintenance records, observed failure modes include: motor trip. Key corrective actions: calibrated, cleaned, tested. |
| Q10 | n/a | n/a | ❌ | extractive | 0.8 | (expected a refusal) | Observed failure patterns include: motor trip. Recorded maintenance actions include: calibrated, cleaned, tested. Relevant measurements incl |
| P1 | n/a | n/a | ✅ | extractive | 0.0 |  | No indexed documents mention C-300, so I can't answer about it. Upload records for that equipment first. |
| P2 | n/a | n/a | ❌ | extractive | 0.77 | (expected a refusal) | Observed failure patterns include: motor trip. Recorded maintenance actions include: calibrated, cleaned, tested. Relevant measurements incl |

## Endpoint checks

| Check | Result | Detail |
|---|---|---|
| Asset 360 returns evidence for P-101 | ✅ | HTTP 200, evidenceChunks=8 |
| RCA for P-101 has evidence-based causes | ✅ | HTTP 200, probableCauses=['bearing failure', 'bearing wear', 'cavitation', 'high vibration'] |
| Analytics lists failure modes | ✅ | HTTP 200, first=[{'failure': 'misalignment', 'count': 5}] |
| Unknown asset C-300 returns 404 | ✅ | HTTP 404 |

## Corpus loaded

| File | HTTP | Status |
|---|---|---|
| compressor-c201-maintenance.txt | 200 | ready |
| operating-readings.csv | 200 | ready |
| pump-p101-inspection-report.txt | 200 | ready |
| pump-p101-maintenance-history.txt | 200 | ready |
| pump-p101-oem-manual.txt | 200 | ready |
| safety-sop.txt | 200 | ready |
