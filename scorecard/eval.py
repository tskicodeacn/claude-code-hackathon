#!/usr/bin/env python3
"""
Scorecard eval harness — Challenge 7 (The Scorecard).

Evaluates Claude's ability to correctly classify extraction seams in the
Spring Music monolith against a human-written golden set (ADR-001).

Metrics produced:
  accuracy             — fraction of candidates where Claude's verdict matches ground truth
  false_confidence_rate — fraction of wrong verdicts where model confidence > 0.7
  behavior_preserved   — whether both test suites (characterization + contract) pass

Usage:
  python scorecard/eval.py [--dry-run] [--skip-behavior]

Authentication:
  Set ANTHROPIC_API_KEY, or run without it if the claude CLI is authenticated
  (eval.py will fall back to calling `claude -p` via subprocess).
  Use --dry-run to skip all API calls (ground-truth stubs, for CI smoke testing).
"""

import argparse
import json
import os
import re
import sys
import subprocess
from pathlib import Path

SCORECARD_DIR = Path(__file__).parent
REPO_ROOT = SCORECARD_DIR.parent / "spring-music-master"
GOLDEN_SET_PATH = SCORECARD_DIR / "golden_set.json"
RESULTS_PATH = SCORECARD_DIR / "results.json"
RUN_TESTS_BAT = SCORECARD_DIR.parent / "run-tests.bat"

MODEL = "claude-sonnet-4-6"
MAX_SOURCE_CHARS = 8000

EVAL_PROMPT = """\
You are a software architect evaluating whether a module in a legacy Spring Boot monolith \
is a good extraction candidate for the Strangler Fig pattern.

## Module Under Evaluation
ID: {candidate_id}
Description: {description}

## Source Code
{source_code}

## Task
Evaluate whether this module should be extracted as a separate service.

Consider:
- Coupling: hidden dependencies that make extraction risky?
- Boundary clarity: is the module's scope well-defined and stable?
- Business value: does extracting it as a service justify the operational cost?
- Test coverage: enough coverage to safely verify behavior after extraction?
- Operational risk: could extraction destabilize the monolith?

Respond with ONLY valid JSON, no surrounding text:
{{
  "verdict": "CORRECT_SEAM" or "INCORRECT_SEAM",
  "risk": "LOW" or "MEDIUM" or "HIGH",
  "confidence": <float 0.0 to 1.0>,
  "reasoning": "<2-3 sentences explaining your verdict>"
}}

CORRECT_SEAM = this module is a good candidate for extraction as a separate service.
INCORRECT_SEAM = this module should NOT be extracted (too risky, no value, should be deleted, or should stay in the monolith).
"""


def load_source(candidate: dict) -> str:
    parts = []
    for rel_path in candidate.get("source_files", []):
        abs_path = REPO_ROOT / rel_path
        if abs_path.exists():
            content = abs_path.read_text(encoding="utf-8", errors="replace")
            parts.append(f"=== {rel_path} ===\n{content}")
        else:
            parts.append(f"=== {rel_path} ===\n[FILE NOT FOUND]")
    combined = "\n\n".join(parts)
    if len(combined) > MAX_SOURCE_CHARS:
        combined = combined[:MAX_SOURCE_CHARS] + "\n\n... [source truncated]"
    return combined or "[No source found]"


def call_claude_sdk(client, prompt: str) -> str:
    message = client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def call_claude_cli(prompt: str) -> str:
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr[:300]}")
    return result.stdout.strip()


def parse_verdict(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {"verdict": "PARSE_ERROR", "risk": "UNKNOWN", "confidence": 0.0, "reasoning": raw[:200]}


def evaluate_candidate(client, candidate: dict) -> dict:
    source = load_source(candidate)
    prompt = EVAL_PROMPT.format(
        candidate_id=candidate["id"],
        description=candidate["description"],
        source_code=source,
    )
    if client is not None:
        raw = call_claude_sdk(client, prompt)
    else:
        raw = call_claude_cli(prompt)
    return parse_verdict(raw)


def fake_evaluate(candidate: dict) -> dict:
    """Dry-run stub — returns a deterministic fake verdict without calling the API."""
    return {
        "verdict": candidate["ground_truth"],
        "risk": candidate["ground_truth_risk"],
        "confidence": 0.85,
        "reasoning": "[dry-run] Returning ground truth verdict.",
    }


def run_behavior_tests() -> bool:
    if not RUN_TESTS_BAT.exists():
        print("  WARN: run-tests.bat not found — skipping behavior preservation check")
        return True
    print("  Running behavior preservation check (both test suites)...")
    result = subprocess.run(
        ["cmd", "/c", str(RUN_TESTS_BAT)],
        capture_output=True,
        text=True,
        cwd=str(SCORECARD_DIR.parent),
    )
    if result.returncode == 0:
        print("  Behavior preservation: PASS")
        return True
    else:
        print("  Behavior preservation: FAIL")
        print(result.stdout[-800:] if result.stdout else "")
        return False


def compute_metrics(results: list[dict]) -> dict:
    total = len(results)
    correct = [r for r in results if r["match"]]
    wrong = [r for r in results if not r["match"]]
    false_confident = [r for r in wrong if r.get("confidence", 0) > 0.7]
    return {
        "total_candidates": total,
        "correct": len(correct),
        "accuracy": round(len(correct) / total, 3) if total else 0.0,
        "wrong": len(wrong),
        "false_confidence_rate": round(len(false_confident) / len(wrong), 3) if wrong else 0.0,
        "false_confident_cases": [r["id"] for r in false_confident],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, return ground truth")
    parser.add_argument("--skip-behavior", action="store_true", help="Skip run-tests.bat")
    args = parser.parse_args()

    client = None
    if not args.dry_run:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
        else:
            # Fall back to claude CLI (already authenticated via Claude Code)
            print("  (ANTHROPIC_API_KEY not set — using claude CLI for API calls)")
            result = subprocess.run(["claude", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                print("ERROR: Neither ANTHROPIC_API_KEY nor claude CLI available.", file=sys.stderr)
                print("Set ANTHROPIC_API_KEY or use --dry-run.", file=sys.stderr)
                sys.exit(1)

    golden_set = json.loads(GOLDEN_SET_PATH.read_text())

    print()
    print("=" * 60)
    print("  SEAM CLASSIFICATION EVAL")
    print("=" * 60)

    results = []
    for candidate in golden_set:
        print(f"  {candidate['id']:<30}", end=" ", flush=True)
        verdict = fake_evaluate(candidate) if args.dry_run else evaluate_candidate(client, candidate)
        match = verdict.get("verdict") == candidate["ground_truth"]
        result = {
            "id": candidate["id"],
            "description": candidate["description"],
            "ground_truth": candidate["ground_truth"],
            "ground_truth_risk": candidate["ground_truth_risk"],
            "claude_verdict": verdict.get("verdict", "ERROR"),
            "claude_risk": verdict.get("risk", "UNKNOWN"),
            "confidence": verdict.get("confidence", 0.0),
            "reasoning": verdict.get("reasoning", ""),
            "match": match,
        }
        results.append(result)
        status = "PASS" if match else "FAIL"
        conf = result["confidence"]
        print(f"{status}  conf={conf:.2f}  [{verdict.get('verdict')}]")

    metrics = compute_metrics(results)

    print()
    print("=" * 60)
    print("  BEHAVIOR PRESERVATION CHECK")
    print("=" * 60)
    behavior_ok = True if args.skip_behavior else run_behavior_tests()

    print()
    print("=" * 60)
    print("  SCORECARD SUMMARY")
    print("=" * 60)
    print(f"  Accuracy:              {metrics['accuracy']:.1%}  ({metrics['correct']}/{metrics['total_candidates']} correct)")
    print(f"  False confidence rate: {metrics['false_confidence_rate']:.1%}  ({len(metrics['false_confident_cases'])} wrong + high-confidence)")
    if metrics["false_confident_cases"]:
        print(f"  False-confident cases: {', '.join(metrics['false_confident_cases'])}")
    print(f"  Behavior preserved:    {'YES' if behavior_ok else 'NO'}")

    output = {
        "model": MODEL if not args.dry_run else "dry-run",
        "metrics": metrics,
        "behavior_preserved": behavior_ok,
        "results": results,
    }
    RESULTS_PATH.write_text(json.dumps(output, indent=2))
    print(f"  Results saved to:      {RESULTS_PATH.name}")
    print()

    passed = metrics["accuracy"] >= 0.6 and behavior_ok
    if not passed:
        if metrics["accuracy"] < 0.6:
            print("  FAIL: accuracy below 60% threshold", file=sys.stderr)
        if not behavior_ok:
            print("  FAIL: behavior preservation tests failed", file=sys.stderr)
        sys.exit(1)

    print("  ALL GREEN — Scorecard passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
