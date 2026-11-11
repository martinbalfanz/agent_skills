#!/usr/bin/env python3
"""Opt-in local progress ledger and Py-FSRS review scheduling for socratic-tutor.

No network, accounts, implicit paths, or automatic syncing. Python 3.10+.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile

VERSION = 1
KINDS = ("guided", "independent", "delayed", "edge", "teach")
RATINGS = {"again": "Again", "hard": "Hard", "good": "Good", "easy": "Easy"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fsrs_types():
    try:
        from fsrs import Card, Rating, Scheduler
    except ImportError as exc:
        raise ValueError("FSRS is unavailable. Install with: python -m pip install 'fsrs>=6,<7>'") from exc
    return Card, Rating, Scheduler


def validate(data: object) -> dict:
    if not isinstance(data, dict) or data.get("version") != VERSION:
        raise ValueError(f"Unsupported state format (expected version {VERSION})")
    if not isinstance(data.get("topic"), str) or not isinstance(data.get("skills"), dict) or not isinstance(data.get("cards"), dict):
        raise ValueError("Malformed state (topic, skills, cards)")
    if not data["topic"].strip():
        raise ValueError("Empty topic")
    for sid, item in data["skills"].items():
        if not isinstance(sid, str) or not isinstance(item, dict) or type(item.get("level")) is not int or item["level"] not in range(6) or not isinstance(item.get("evidence"), list):
            raise ValueError(f"Malformed skill: {sid}")
    for cid, card in data["cards"].items():
        if not isinstance(card, dict) or card.get("skill") not in data["skills"] or not isinstance(card.get("fsrs"), str) or not isinstance(card.get("cue"), str):
            raise ValueError(f"Malformed card: {cid}")
    return data


def load(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"State not found: {path} (run init first)")
    return validate(json.loads(path.read_text(encoding="utf-8")))


def save(path: Path, data: dict, *, create: bool = False) -> None:
    if create and path.exists():
        raise ValueError(f"Refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = utc_now()
    contents = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(prefix=".socratic-", suffix=".json", dir=path.parent)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
        # Exclusive create ensures a second initializer cannot silently replace state.
        if create:
            try:
                with open(path, "x", encoding="utf-8") as marker:
                    marker.write("")
            except FileExistsError as exc:
                raise ValueError(f"Refusing to overwrite: {path}") from exc
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def require_skill(data: dict, key: str) -> dict:
    if key not in data["skills"]:
        raise ValueError(f"Unknown skill: {key}")
    return data["skills"][key]


def status(data: dict) -> dict:
    now = datetime.now(timezone.utc)
    due = []
    for cid, item in data["cards"].items():
        # Avoid importing FSRS just to inspect the due queue.
        card = json.loads(item["fsrs"])
        due_at = card.get("due")
        if not isinstance(due_at, str):
            raise ValueError(f"Malformed due date on card {cid}")
        due_dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        if due_dt.tzinfo is None:
            raise ValueError(f"Card {cid} has a timezone-naive due date")
        if due_dt <= now:
            due.append({"id": cid, "skill": item["skill"], "cue": item["cue"], "due": due_at})
    due.sort(key=lambda i: i["due"])
    return {
        "topic": data["topic"], "updated_at": data["updated_at"],
        "skills": {k: {"level": v["level"], "provisional": v["level"] < 3,
                       "evidence_checks": len(v["evidence"]), "reason": v.get("reason", "")}
                   for k, v in data["skills"].items()},
        "cards_total": len(data["cards"]), "due": due,
    }


def eligible(evidence: list, level: int) -> bool:
    passes = [e for e in evidence if e["result"] == "pass"]
    unique = {e["check"] for e in passes}
    if level <= 2:
        return True
    if level == 3:
        return len(unique) >= 2 and any(e["kind"] in KINDS for e in passes)
    independent = [e for e in passes if e["kind"] in ("independent", "delayed", "edge", "teach")]
    if len({e["check"] for e in independent}) < 2 or not any(e["kind"] == "delayed" for e in passes):
        return False
    if level == 4:
        return True
    edges = {e["check"] for e in passes if e["kind"] == "edge"}
    teaches = {e["check"] for e in passes if e["kind"] == "teach"}
    return bool(edges and teaches and any(e != t for e in edges for t in teaches))


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", required=True, type=Path, help="Explicit path to a local JSON state file")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Create a new study topic (no overwrite)")
    init.add_argument("--topic", required=True)
    init.add_argument("--skill", action="append", required=True, dest="skills")
    sub.add_parser("status", help="Show map and due FSRS cards")
    sub.add_parser("export", help="Print portable full JSON state")
    add = sub.add_parser("add-card", help="Create a retrieval cue")
    add.add_argument("--id", required=True)
    add.add_argument("--skill", required=True)
    add.add_argument("--cue", required=True)
    review = sub.add_parser("review", help="Grade one *answered* retrieval cue")
    review.add_argument("--id", required=True)
    review.add_argument("--rating", choices=RATINGS, required=True)
    ev = sub.add_parser("evidence", help="Record independent check or guided application")
    ev.add_argument("--skill", required=True)
    ev.add_argument("--check", required=True, help="Unique prompt/attempt ID")
    ev.add_argument("--kind", choices=KINDS, required=True)
    ev.add_argument("--result", choices=("pass", "fail"), required=True)
    ev.add_argument("--note", required=True, help="What was observed and how it was verified")
    level = sub.add_parser("level", help="Set an earned mastery level")
    level.add_argument("--skill", required=True)
    level.add_argument("--value", type=int, choices=range(6), required=True)
    level.add_argument("--reason", required=True)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    path = args.state.expanduser()
    if args.command == "init":
        if not args.topic.strip() or any(not s.strip() for s in args.skills) or len(set(args.skills)) != len(args.skills):
            raise ValueError("Topic and skills must be nonempty; skills must be unique")
        data = {"version": VERSION, "topic": args.topic, "created_at": utc_now(),
                "updated_at": utc_now(), "skills": {s: {"level": 0, "reason": "unassessed", "evidence": []} for s in args.skills},
                "cards": {}, "reviews": []}
        save(path, data, create=True)
    else:
        data = load(path)
        if args.command == "status":
            print(json.dumps(status(data), indent=2, ensure_ascii=False))
            return
        if args.command == "export":
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return
        if args.command == "add-card":
            require_skill(data, args.skill)
            if not args.id.strip() or not args.cue.strip() or args.id in data["cards"]:
                raise ValueError("Card ID/cue must be nonempty and the card ID must be new")
            Card, _, _ = fsrs_types()
            data["cards"][args.id] = {"skill": args.skill, "cue": args.cue, "fsrs": Card().to_json()}
        elif args.command == "review":
            if args.id not in data["cards"]:
                raise ValueError(f"Unknown card: {args.id}")
            Card, Rating, Scheduler = fsrs_types()
            entry = data["cards"][args.id]
            card, log = Scheduler().review_card(Card.from_json(entry["fsrs"]), getattr(Rating, RATINGS[args.rating]))
            entry["fsrs"] = card.to_json()
            data["reviews"].append({"id": args.id, "rating": args.rating, "at": utc_now(), "log": log.to_json()})
        elif args.command == "evidence":
            item = require_skill(data, args.skill)
            if not args.check.strip() or not args.note.strip() or any(e["check"] == args.check for e in item["evidence"]):
                raise ValueError("Check ID/note required; check ID must be unique within subskill")
            item["evidence"].append({"check": args.check, "kind": args.kind, "result": args.result, "note": args.note, "at": utc_now()})
        elif args.command == "level":
            item = require_skill(data, args.skill)
            if not args.reason.strip():
                raise ValueError("Level change needs a reason")
            if not eligible(item["evidence"], args.value):
                raise ValueError(f"Insufficient distinct evidence for level {args.value}; see references/STATE.md")
            item["level"] = args.value
            item["reason"] = args.reason
        save(path, data)
    print(json.dumps(status(data), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)