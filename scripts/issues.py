#!/usr/bin/env python3
"""Mirror tracking/tasks/*.md to GitHub issues. Standard library only (+ the `gh` CLI for sync).

The task files are canonical. Issues are a progress view: one issue per task, titled
"[<ID>] <title>", with labels for phase, area, requirements and status. Each phase's
exit gate issue (GATE-Pn) is the parent of that phase's tasks, so GitHub shows a
per-phase progress bar. Issue bodies are regenerated from the task file; edit the file,
not the issue body. Comments on issues are fine.

Usage:
  python3 scripts/issues.py export --start N --out issues.json   # payloads in creation order, numbers predicted from N
  python3 scripts/issues.py apply --map map.json                 # write `issue: N` into task frontmatter from {"ID": N}
  python3 scripts/issues.py labels                               # create/update label colours (needs gh)
  python3 scripts/issues.py sync [--dry-run]                     # create missing issues, update state/labels/body (needs gh)

CI runs `labels` and `sync` on every push to main (.github/workflows/issues-sync.yml).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tasks as T  # noqa: E402

NEEDS_USER = {"windows-sim", "blender", "gpu", "human"}
STATUS_LABELS = [f"status:{s}" for s in T.STATUSES]
LABEL_STYLE = {
    "phase:": ("1d76db", "Phase from plans/05-phases.md"),
    "area:": ("5319e7", "Task area (id prefix)"),
    "requires:": ("c5def5", "Environment the task needs"),
    "status:todo": ("ededed", "Not started"),
    "status:in_progress": ("fbca04", "Claimed and being worked on"),
    "status:blocked": ("d93f0b", "Blocked; see the task Log"),
    "status:review": ("0e8a16", "Implemented, awaiting review"),
    "status:done": ("006b75", "Merged and done"),
    "status:dropped": ("bfbfbf", "Dropped; see the task Log"),
    "needs-user": ("b60205", "Needs the sim PC, Blender, a GPU or the user's judgement"),
    "gate": ("000000", "Phase exit gate; parent of the phase's tasks"),
    "decision": ("f9d0c4", "A decision the user makes (ends in an ADR)"),
}


def repo_slug() -> str:
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    url = subprocess.run(["git", "-C", str(T.ROOT), "remote", "get-url", "origin"],
                         capture_output=True, text=True).stdout.strip()
    m = re.search(r"github\.com[/:]([^/]+/[^/.]+?)(?:\.git)?$", url) or re.search(r"/git/([^/]+/[^/.]+?)(?:\.git)?$", url)
    if not m:
        sys.exit("cannot determine owner/repo; set GITHUB_REPOSITORY")
    return m.group(1)


# --------------------------------------------------------------------------- payloads

def section(body: str, name: str) -> str:
    m = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", body, flags=re.M | re.S)
    return m.group(1).strip() if m else ""


def creation_order(tasks: dict) -> list:
    gates = sorted([t for t in tasks.values() if t.meta.get("area") == "GATE"], key=lambda t: t.meta["phase"])
    rest = sorted([t for t in tasks.values() if t.meta.get("area") != "GATE"],
                  key=lambda t: (t.meta.get("phase", 9), t.id))
    return gates + rest


def labels_for(t) -> list:
    m = t.meta
    req = t.get_list("requires")
    labels = [f"phase:{m['phase']}", f"area:{m['area'].lower()}", f"status:{m['status']}"]
    labels += [f"requires:{r}" for r in req]
    if set(req) & NEEDS_USER:
        labels.append("needs-user")
    if m.get("kind") == "gate":
        labels.append("gate")
    if m.get("kind") == "decision":
        labels.append("decision")
    return labels


def title_for(t) -> str:
    return f"[{t.id}] {t.meta.get('title', '')}"


def body_for(t, numbers: dict, repo: str) -> str:
    m = t.meta
    base = f"https://github.com/{repo}/blob/main/"
    plan = str(m.get("plan_ref", ""))
    plan_path, _, anchor = plan.partition("#")
    plan_link = f"[{plan}]({base}{plan_path}{'#' + anchor if anchor else ''})" if plan else "-"
    lines = [
        f"**Task file:** [tracking/tasks/{t.id}.md]({base}tracking/tasks/{t.id}.md) · **Plan:** {plan_link}",
        "",
        f"**Phase** {m.get('phase')} · **Area** {m.get('area')} · **Kind** {m.get('kind')} · "
        f"**Requires** {', '.join(t.get_list('requires'))} · **Agent** `{m.get('agent')}` · "
        f"**Estimate** {m.get('estimate_h')} h",
        "",
    ]
    goal = section(t.body, "Goal")
    if len(goal) > 1500:
        goal = goal[:1500].rsplit(" ", 1)[0] + " … (see task file)"
    lines += ["### Goal", "", goal or "_See task file._", ""]
    ac = section(t.body, "Acceptance criteria")
    if ac:
        if len(ac) > 3000:
            ac = ac[:3000].rsplit("\n", 1)[0] + "\n- … (more in the task file)"
        lines += ["### Acceptance criteria", "", ac, ""]
    deps = t.get_list("depends_on")
    if deps:
        lines += ["### Depends on", ""]
        for d in deps:
            ref = f"#{numbers[d]}" if d in numbers else "(no issue yet)"
            lines.append(f"- {ref} `{d}`")
        lines.append("")
    lines.append("<sub>Generated from the task file, which is canonical. Status, labels and this body "
                 "sync from the file on every push to `main` (`scripts/issues.py`). Comment freely; "
                 "edit the task file, not this body.</sub>")
    return "\n".join(lines)


def gate_parent(t, numbers: dict):
    if t.meta.get("area") == "GATE":
        return None
    return numbers.get(f"GATE-P{t.meta.get('phase')}")


# --------------------------------------------------------------------------- gh helpers

def gh_exe() -> str:
    """The gh CLI: $GH, else gh on PATH, else the default Windows install location."""
    found = os.environ.get("GH") or shutil.which("gh")
    win = Path(r"C:\Program Files\GitHub CLI\gh.exe")
    return found or (str(win) if win.exists() else "gh")


def gh(*args, input_text=None, check=True) -> str:
    r = subprocess.run([gh_exe(), *args], capture_output=True, text=True, input=input_text,
                       encoding="utf-8")
    if check and r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])} failed: {r.stderr.strip()}")
    return r.stdout


def existing_issues(repo: str) -> dict:
    out = gh("issue", "list", "--repo", repo, "--state", "all", "--limit", "2000",
             "--json", "number,title,state,labels,body")
    found = {}
    for it in json.loads(out):
        m = re.match(r"^\[([A-Z]+-(?:\d{3}|P\d))\]", it["title"])
        if m:
            found[m.group(1)] = it
    return found


# --------------------------------------------------------------------------- commands

def cmd_export(a):
    tasks = T.load_all()
    repo = repo_slug()
    order = creation_order(tasks)
    numbers = {t.id: a.start + i for i, t in enumerate(order)}
    out = []
    for t in order:
        out.append({"id": t.id, "number": numbers[t.id], "title": title_for(t), "labels": labels_for(t),
                    "parent": gate_parent(t, numbers), "body": body_for(t, numbers, repo)})
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {len(out)} payloads to {a.out} (numbers {a.start}..{a.start + len(out) - 1})")


def cmd_apply(a):
    mapping = json.loads(Path(a.map).read_text(encoding="utf-8"))
    tasks = T.load_all()
    n = 0
    for tid, num in mapping.items():
        t = tasks.get(tid)
        if t is None:
            print(f"skip unknown {tid}")
            continue
        if t.meta.get("issue") != int(num):
            t.set("issue", int(num))
            text = "---\n" + "\n".join(t.fm_lines) + "\n---\n" + t.body
            t.path.write_text(text, encoding="utf-8")
            n += 1
    print(f"updated {n} task files")


def cmd_labels(a):
    repo = repo_slug()
    tasks = T.load_all()
    names = sorted({l for t in tasks.values() for l in labels_for(t)} | set(STATUS_LABELS))
    for name in names:
        color, desc = next(((c, d) for k, (c, d) in LABEL_STYLE.items() if name == k or (k.endswith(":") and name.startswith(k))),
                           ("ededed", ""))
        gh("label", "create", name, "--repo", repo, "--color", color, "--description", desc, "--force")
    print(f"{len(names)} labels ensured")


def cmd_sync(a):
    repo = repo_slug()
    tasks = T.load_all()
    have = existing_issues(repo)
    numbers = {tid: it["number"] for tid, it in have.items()}
    created = 0
    # create missing issues (gates first, so parents exist)
    for t in creation_order(tasks):
        if t.id in have:
            continue
        body = body_for(t, numbers, repo)
        args = ["issue", "create", "--repo", repo, "--title", title_for(t), "--body-file", "-"]
        for l in labels_for(t):
            args += ["--label", l]
        if a.dry_run:
            print(f"would create {t.id}")
            continue
        url = gh(*args, input_text=body).strip()
        num = int(url.rstrip("/").split("/")[-1])
        numbers[t.id] = num
        have[t.id] = {"number": num, "title": title_for(t), "state": "OPEN",
                      "labels": [{"name": l} for l in labels_for(t)], "body": body}
        parent = gate_parent(t, numbers)
        if parent:
            sub_id = gh("api", f"repos/{repo}/issues/{num}", "--jq", ".id").strip()
            gh("api", "-X", "POST", f"repos/{repo}/issues/{parent}/sub_issues", "-F", f"sub_issue_id={sub_id}", check=False)
        created += 1
        print(f"created #{num} {t.id}")
    updated = 0
    for t in creation_order(tasks):
        it = have.get(t.id)
        if not it:
            continue
        num = it["number"]
        want_labels = set(labels_for(t))
        cur_labels = {l["name"] for l in it.get("labels", [])}
        managed = lambda l: l.startswith(("phase:", "area:", "requires:", "status:")) or l in ("needs-user", "gate", "decision")
        add = sorted(want_labels - cur_labels)
        remove = sorted(l for l in cur_labels - want_labels if managed(l))
        want_body = body_for(t, numbers, repo)
        edits = []
        if it["title"] != title_for(t):
            edits += ["--title", title_for(t)]
        for l in add:
            edits += ["--add-label", l]
        for l in remove:
            edits += ["--remove-label", l]
        norm = lambda x: (x or "").replace("\r\n", "\n").strip()
        body_changed = norm(it.get("body")) != norm(want_body)
        want_closed = t.meta.get("status") in ("done", "dropped")
        is_closed = it["state"].upper() == "CLOSED"
        if not edits and not body_changed and want_closed == is_closed:
            continue
        if a.dry_run:
            print(f"would update #{num} {t.id}: labels+{add} -{remove} body={body_changed} closed={want_closed}")
            continue
        if edits or body_changed:
            args = ["issue", "edit", str(num), "--repo", repo, *edits]
            if body_changed:
                with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
                    f.write(want_body)
                args += ["--body-file", f.name]
            gh(*args)
        if want_closed and not is_closed:
            reason = "not planned" if t.meta.get("status") == "dropped" else "completed"
            gh("issue", "close", str(num), "--repo", repo, "--reason", reason)
        elif not want_closed and is_closed:
            gh("issue", "reopen", str(num), "--repo", repo)
        updated += 1
        print(f"updated #{num} {t.id}")
    print(f"sync: {created} created, {updated} updated")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--start", type=int, required=True, help="number the first created issue will get")
    e.add_argument("--out", required=True)
    p = sub.add_parser("apply")
    p.add_argument("--map", required=True)
    sub.add_parser("labels")
    s = sub.add_parser("sync")
    s.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    {"export": cmd_export, "apply": cmd_apply, "labels": cmd_labels, "sync": cmd_sync}[a.cmd](a)


if __name__ == "__main__":
    main()
