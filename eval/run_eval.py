"""IndusMind evaluation harness (stdlib only, so it runs against any server build).

Asks every question in eval/benchmark.jsonl through the real HTTP API, checks retrieval,
answer content and refusals, probes the Asset 360 / RCA / Analytics endpoints, and writes
a JSON + Markdown report to eval/reports/.

The answer check is a minimum bar (required keywords present), not a quality judge: it is
cheap, deterministic and comparable across versions.

Usage (server already running):
    set EVAL_USERNAME=...  &  set EVAL_PASSWORD=...
    python eval/run_eval.py --base-url http://127.0.0.1:8000 --label after-phase0
    python eval/run_eval.py --base-url http://127.0.0.1:8010 --label baseline --load-corpus sample-data
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFUSAL_MARKERS = (
    "insufficient evidence", "could not find", "no indexed evidence", "not enough evidence",
    "no evidence", "not available in", "cannot answer", "not found in",
)


class Api:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.token = ""

    def request(self, method: str, path: str, body: bytes | None = None,
                content_type: str = "application/json", timeout: int = 120):
        req = urllib.request.Request(self.base + path, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", content_type)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw.startswith((b"{", b"[")) else raw
        except urllib.error.HTTPError as err:
            raw = err.read()
            try:
                return err.code, json.loads(raw)
            except ValueError:
                return err.code, raw.decode("utf-8", "replace")

    def post_json(self, path: str, payload: dict):
        return self.request("POST", path, json.dumps(payload).encode("utf-8"))

    def upload(self, path: str, file_path: Path):
        boundary = uuid.uuid4().hex
        mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{file_path.name}\"\r\nContent-Type: {mime}\r\n\r\n"
        ).encode("utf-8") + file_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
        return self.request("POST", path, body, f"multipart/form-data; boundary={boundary}", timeout=300)


def is_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def grade(item: dict, answer: str, citations: list[dict]) -> dict:
    sources = [c.get("filename") or c.get("source") or "" for c in citations]
    lowered = f" {answer.lower()} "
    refused = is_refusal(answer)
    if item.get("should_refuse"):
        return {"retrieval_hit": None, "top1_hit": None, "answer_pass": refused, "refused": refused,
                "missing": [] if refused else ["(expected a refusal)"], "sources": sources}
    expected = set(item.get("expected_sources", []))
    missing = [group[0] for group in item.get("must_mention", [])
               if not any(token.lower() in lowered for token in group)]
    return {
        "retrieval_hit": bool(expected & set(sources)),
        "top1_hit": bool(sources) and sources[0] in expected,
        "answer_pass": not missing and not refused,
        "refused": refused,
        "missing": missing,
        "sources": sources,
    }


def endpoint_checks(api: Api) -> list[dict]:
    checks = []
    status, body = api.request("GET", "/api/assets/P-101")
    ok = status == 200 and isinstance(body, dict) and body.get("evidenceChunks", 0) > 0
    checks.append({"check": "Asset 360 returns evidence for P-101", "pass": ok,
                   "detail": f"HTTP {status}, evidenceChunks={body.get('evidenceChunks') if isinstance(body, dict) else 'n/a'}"})

    status, body = api.request("POST", "/api/rca/P-101")
    causes = body.get("probableCauses", []) if isinstance(body, dict) else []
    ok = status == 200 and bool(causes) and not any("insufficient" in c.lower() for c in causes)
    checks.append({"check": "RCA for P-101 has evidence-based causes", "pass": ok,
                   "detail": f"HTTP {status}, probableCauses={causes[:4]}"})

    status, body = api.request("GET", "/api/analytics")
    modes = body.get("topFailureModes", []) if isinstance(body, dict) else []
    ok = status == 200 and bool(modes)
    checks.append({"check": "Analytics lists failure modes", "pass": ok,
                   "detail": f"HTTP {status}, first={modes[:1]}"})

    status, body = api.request("GET", "/api/assets/C-300")
    checks.append({"check": "Unknown asset C-300 returns 404", "pass": status == 404, "detail": f"HTTP {status}"})
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--label", required=True, help="report name, e.g. baseline or after-phase0")
    parser.add_argument("--load-corpus", help="upload every file in this folder before asking")
    parser.add_argument("--benchmark", default=str(ROOT / "eval" / "benchmark.jsonl"))
    parser.add_argument("--out", default=str(ROOT / "eval" / "reports"))
    args = parser.parse_args()

    username, password = os.environ.get("EVAL_USERNAME"), os.environ.get("EVAL_PASSWORD")
    if not username or not password:
        print("Set EVAL_USERNAME and EVAL_PASSWORD (a user that exists on the target server).", file=sys.stderr)
        return 2

    api = Api(args.base_url)
    status, body = api.post_json("/api/auth/login", {"username": username, "password": password})
    if status != 200:
        print(f"Login failed: HTTP {status} {body}", file=sys.stderr)
        return 1
    api.token = body["token"]

    uploads = []
    if args.load_corpus:
        for file_path in sorted(p for p in Path(args.load_corpus).iterdir() if p.is_file()):
            status, body = api.upload("/api/documents/upload", file_path)
            uploads.append({"file": file_path.name, "http": status,
                            "status": body.get("status") if isinstance(body, dict) else body})

    items = [json.loads(line) for line in Path(args.benchmark).read_text(encoding="utf-8").splitlines() if line.strip()]
    results = []
    for item in items:
        started = time.perf_counter()
        status, body = api.post_json("/api/chat/query", {"question": item["question"], "desiredFormat": "quick_answer"})
        latency_ms = round((time.perf_counter() - started) * 1000)
        body = body if isinstance(body, dict) else {}
        answer = str(body.get("answer", ""))
        result = {"id": item["id"], "kind": item["kind"], "question": item["question"], "http": status,
                  "latency_ms": latency_ms, "mode": body.get("mode"), "confidence": body.get("confidence"),
                  "answer": answer, **grade(item, answer, body.get("citations", []))}
        results.append(result)

    checks = endpoint_checks(api)
    answerable = [r for r in results if r["retrieval_hit"] is not None]
    refusal_items = [r for r in results if r["retrieval_hit"] is None]
    summary = {
        "retrieval_hit_rate": f"{sum(r['retrieval_hit'] for r in answerable)}/{len(answerable)}",
        "top1_source_correct": f"{sum(r['top1_hit'] for r in answerable)}/{len(answerable)}",
        "answer_pass": f"{sum(r['answer_pass'] for r in results if r['kind'] == 'benchmark')}/{sum(r['kind'] == 'benchmark' for r in results)}",
        "correct_refusals": f"{sum(r['answer_pass'] for r in refusal_items)}/{len(refusal_items)}",
        "false_refusals": sum(r["refused"] for r in answerable),
        "endpoint_checks": f"{sum(c['pass'] for c in checks)}/{len(checks)}",
        "median_latency_ms": sorted(r["latency_ms"] for r in results)[len(results) // 2],
    }
    report = {"label": args.label, "date": date.today().isoformat(), "base_url": args.base_url,
              "summary": summary, "uploads": uploads, "results": results, "endpoint_checks": checks}

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{report['date']}-{args.label}"
    (out_dir / f"{stem}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / f"{stem}.md").write_text(to_markdown(report), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"Report: {out_dir / (stem + '.md')}")
    return 0


def to_markdown(report: dict) -> str:
    s = report["summary"]
    lines = [
        f"# Eval report: {report['label']} ({report['date']})", "",
        f"Server: `{report['base_url']}`", "",
        "| Metric | Result |", "|---|---|",
        f"| Correct source anywhere in top-5 citations (answerable) | {s['retrieval_hit_rate']} |",
        f"| Correct source as the FIRST citation (answerable) | {s['top1_source_correct']} |",
        f"| Benchmark answers containing the required facts | {s['answer_pass']} |",
        f"| Correct refusals (Q10 + honesty probes) | {s['correct_refusals']} |",
        f"| False refusals on answerable questions | {s['false_refusals']} |",
        f"| Endpoint checks (Asset 360, RCA, Analytics, unknown asset) | {s['endpoint_checks']} |",
        f"| Median latency | {s['median_latency_ms']} ms |", "",
        "## Questions", "",
        "| ID | Top-5 | Top-1 | Answer | Mode | Conf. | Missing / note | Answer (first 140 chars) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in report["results"]:
        hit = "n/a" if r["retrieval_hit"] is None else ("✅" if r["retrieval_hit"] else "❌")
        top1 = "n/a" if r["top1_hit"] is None else ("✅" if r["top1_hit"] else "❌")
        ans = "✅" if r["answer_pass"] else "❌"
        snippet = r["answer"].replace("\n", " ").replace("|", "\\|")[:140]
        lines.append(f"| {r['id']} | {hit} | {top1} | {ans} | {r['mode']} | {r['confidence']} | "
                     f"{', '.join(r['missing']) or ''} | {snippet} |")
    lines += ["", "## Endpoint checks", "", "| Check | Result | Detail |", "|---|---|---|"]
    for c in report["endpoint_checks"]:
        detail = str(c["detail"]).replace("|", "\\|")[:160]
        lines.append(f"| {c['check']} | {'✅' if c['pass'] else '❌'} | {detail} |")
    if report["uploads"]:
        lines += ["", "## Corpus loaded", "", "| File | HTTP | Status |", "|---|---|---|"]
        lines += [f"| {u['file']} | {u['http']} | {u['status']} |" for u in report["uploads"]]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
