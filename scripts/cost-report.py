#!/usr/bin/env python3
"""cost-report.py — what did the agents spend, per task and per model?

Reads Claude Code's local session transcripts for this repository (and its agent worktrees):
  ~/.claude/projects/<repo-path-with-non-alphanumerics-as-dashes>*/<session>.jsonl
  ~/.claude/projects/<...>/<session>/subagents/agent-<id>.jsonl (+ .meta.json: agent type)

Every assistant response records its model and token usage. The task comes from the subagent's
launch description, which the conductor always starts with the issue number ("#42 implement ...",
see .claude/skills/implement). Fallback: a task branch name (feat/42-x -> #42). Claude Code
records the branch only when a session starts, so the description is the reliable tag.

CAVEATS (printed with every report):
* Claude Code documents the transcript format as internal and version-dependent. This script
  checks for the fields it needs and stops with an error if they are missing, instead of
  printing wrong numbers. The stable alternative is Claude Code's OpenTelemetry metrics
  (claude_code.cost.usage / claude_code.token.usage).
* One API response can span several transcript lines that repeat the same usage; responses
  are de-duplicated by (message id, request id).
* Costs are estimates at API list price (tools/model-prices.toml), not an invoice.

Usage: cost-report.py [--since YYYY-MM-DD] [--issue N] [--root PATH]
Standard library only (python 3.11+ for tomllib).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

TOKEN_KINDS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")
TASK_RE = re.compile(r"^[a-z]+/(\d+)-")
DESC_TASK_RE = re.compile(r"^#(\d+)\b")


@dataclass
class Tally:
    tokens: dict[str, int] = field(default_factory=lambda: dict.fromkeys(TOKEN_KINDS, 0))
    cost: float = 0.0
    responses: int = 0
    unpriced: int = 0

    def add(self, usage: dict[str, int], cost: float | None) -> None:
        for k in TOKEN_KINDS:
            self.tokens[k] += usage[k]
        self.responses += 1
        if cost is None:
            self.unpriced += 1
        else:
            self.cost += cost


def project_dirs(root: Path) -> list[Path]:
    """Transcript folders for the repo and any worktree inside it (e.g. .claude/worktrees/...)."""
    base = Path.home() / ".claude" / "projects"
    prefix = re.sub(r"[^A-Za-z0-9]", "-", str(root.resolve()))
    return sorted(p for p in base.glob("*") if p.is_dir() and p.name.startswith(prefix))


def transcripts(dirs: list[Path]):
    """Yield (path, agent_label, task_from_description) for main sessions and their subagents."""
    for d in dirs:
        for f in sorted(d.glob("*.jsonl")):
            yield f, "conductor", None
        for f in sorted(d.glob("*/subagents/*.jsonl")):
            meta = f.with_suffix(".meta.json")
            label, task = "subagent", None
            if meta.exists():
                try:
                    info = json.loads(meta.read_text())
                    label = info.get("agentType") or label
                    m = DESC_TASK_RE.match(str(info.get("description") or ""))
                    task = f"#{m.group(1)}" if m else None
                except (OSError, json.JSONDecodeError):
                    pass
            yield f, label, task


def usage_of(raw: dict) -> dict[str, int]:
    split = raw.get("cache_creation") or {}
    w1h = int(split.get("ephemeral_1h_input_tokens") or 0)
    w5m = int(split.get("ephemeral_5m_input_tokens") or 0)
    total_w = int(raw.get("cache_creation_input_tokens") or 0)
    if w1h + w5m == 0:
        w5m = total_w                      # no split reported: assume the default 5-minute TTL
    return {
        "input": int(raw.get("input_tokens") or 0),
        "output": int(raw.get("output_tokens") or 0),
        "cache_write_5m": w5m,
        "cache_write_1h": w1h,
        "cache_read": int(raw.get("cache_read_input_tokens") or 0),
    }


def cost_of(model: str, u: dict[str, int], prices: dict) -> float | None:
    p = prices.get(model)
    if p is None:
        return None
    prompt = u["input"] + u["cache_read"] + u["cache_write_5m"] + u["cache_write_1h"]
    long_ctx = "long_context_threshold" in p and prompt > p["long_context_threshold"]
    rate_in = p["long_input"] if long_ctx else p["input"]
    rate_out = p["long_output"] if long_ctx else p["output"]
    return (u["input"] * rate_in + u["output"] * rate_out + u["cache_write_5m"] * p["cache_write_5m"]
            + u["cache_write_1h"] * p["cache_write_1h"] + u["cache_read"] * p["cache_read"]) / 1e6


def fmt_tokens(n: int) -> str:
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.1f}k" if n >= 1e3 else str(n)


def table(title: str, rows: dict, grand: float) -> None:
    print(f"\n{title}")
    print(f"  {'':34} {'responses':>9} {'input':>8} {'output':>8} {'cache wr':>8} {'cache rd':>8} {'est. $':>9} {'share':>6}")
    for key, t in sorted(rows.items(), key=lambda kv: -kv[1].cost):
        name = " · ".join(key) if isinstance(key, tuple) else key
        wr = t.tokens["cache_write_5m"] + t.tokens["cache_write_1h"]
        share = f"{100 * t.cost / grand:5.1f}%" if grand else "   -"
        flag = " (?)" if t.unpriced else ""
        print(f"  {name[:34]:34} {t.responses:9} {fmt_tokens(t.tokens['input']):>8} {fmt_tokens(t.tokens['output']):>8}"
              f" {fmt_tokens(wr):>8} {fmt_tokens(t.tokens['cache_read']):>8} {t.cost:9.2f} {share:>6}{flag}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", help="only responses on/after this date (YYYY-MM-DD)")
    ap.add_argument("--issue", type=int, help="only this task (issue number)")
    ap.add_argument("--root", default=Path(__file__).resolve().parent.parent, type=Path)
    args = ap.parse_args()

    prices = tomllib.loads((args.root / "tools" / "model-prices.toml").read_text())["models"]
    dirs = project_dirs(args.root)
    if not dirs:
        print(f"no Claude Code transcripts found for {args.root}", file=sys.stderr)
        return 1

    seen: set[tuple[str, str]] = set()
    by_model: dict[str, Tally] = defaultdict(Tally)
    by_task: dict[tuple[str, str], Tally] = defaultdict(Tally)
    by_agent: dict[tuple[str, str], Tally] = defaultdict(Tally)
    total = Tally()
    assistant_lines = malformed = 0

    for path, agent, desc_task in transcripts(dirs):
        for line in path.open(encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "assistant":
                continue
            assistant_lines += 1
            msg = d.get("message")
            if not isinstance(msg, dict) or "model" not in msg or "usage" not in msg:
                malformed += 1
                continue
            key = (str(msg.get("id")), str(d.get("requestId")))
            if key in seen:
                continue                    # same response written as several lines
            seen.add(key)
            if args.since and str(d.get("timestamp", ""))[:10] < args.since:
                continue
            m = TASK_RE.match(str(d.get("gitBranch") or ""))
            task = desc_task or (f"#{m.group(1)}" if m else "(planning / no task)")
            if args.issue is not None and task != f"#{args.issue}":
                continue
            model = msg["model"]
            u = usage_of(msg["usage"])
            c = cost_of(model, u, prices)
            for tally in (by_model[model], by_task[(task, model)], by_agent[(agent, model)], total):
                tally.add(u, c)

    if assistant_lines and malformed / assistant_lines > 0.05:
        print(f"error: {malformed} of {assistant_lines} assistant entries lack model/usage. The Claude Code "
              "transcript format has probably changed; update scripts/cost-report.py.", file=sys.stderr)
        return 2

    scope = f"task #{args.issue}" if args.issue is not None else "all tasks"
    print(f"Agent spend for {args.root.name} — {scope}{', since ' + args.since if args.since else ''}")
    print(f"{total.responses} API responses from {len(dirs)} transcript folder(s); "
          f"estimated ${total.cost:.2f} at list price")
    table("By model", by_model, total.cost)
    table("By agent · model", by_agent, total.cost)
    table("By task · model", by_task, total.cost)
    if total.unpriced:
        print(f"\n(?) {total.unpriced} responses used a model missing from tools/model-prices.toml (counted as $0).")
    print("\nEstimates at API list price from local transcripts (internal format; see script header).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
