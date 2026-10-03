"""Persistent student memory: who they are + what they studied (JSON per student)."""
import json, re
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def _path(name: str) -> Path:
    return DATA / f"{re.sub(r'[^a-z0-9_-]', '_', name.lower().strip() or 'guest')}.json"


def load(name: str) -> dict:
    p = _path(name)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {"name": name, "sessions": [], "weak_concepts": []}


def save(profile: dict) -> None:
    DATA.mkdir(exist_ok=True)
    _path(profile["name"]).write_text(json.dumps(profile, indent=2))


def summarize(profile: dict) -> str:
    if not profile["sessions"]:
        return "New student, no history."
    last = profile["sessions"][-3:]
    topics = "; ".join(f"{s['topic']} ({s['level']}, {s['score']:.0%})" for s in last)
    weak = ", ".join(profile["weak_concepts"][-5:]) or "none"
    return f"Recent topics: {topics}. Previously weak concepts: {weak}."


def record(profile: dict, topic: str, level: str, score: float, weak: list) -> None:
    profile["sessions"].append({"topic": topic, "level": level, "score": score})
    profile["weak_concepts"] = list(dict.fromkeys(profile["weak_concepts"] + weak))[-20:]
    save(profile)
