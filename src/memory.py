import json
import random
import re
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEMORY_PATH = PROJECT_ROOT / "data" / "student_memory.json"

DEFAULT_MEMORY = {
    "weak_topics": [],
    "strong_topics": [],
    "recent_quizzes": [],
    "notes": [],
    "score": 0,
    "high_score": 0,
}


def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return {key: (list(value) if isinstance(value, list) else value) for key, value in DEFAULT_MEMORY.items()}
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {key: (list(value) if isinstance(value, list) else value) for key, value in DEFAULT_MEMORY.items()}
    for key, default in DEFAULT_MEMORY.items():
        data.setdefault(key, list(default) if isinstance(default, list) else default)
    return data


def save_memory(data: dict) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def clear_memory() -> None:
    save_memory(
        {
            "weak_topics": [],
            "strong_topics": [],
            "recent_quizzes": [],
            "notes": [],
            "score": 0,
            "high_score": 0,
        }
    )


def get_score() -> int:
    return int(load_memory().get("score", 0))


def reset_score() -> int:
    data = load_memory()
    data["score"] = 0
    save_memory(data)
    return 0


def _normalize_topic(topic: str) -> str:
    return re.sub(r"\s+", " ", topic.strip())


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def add_quiz_result(topic: str, verdict: str, points: int = 0) -> int:
    """Update topics/score. Returns new total score."""
    topic = _normalize_topic(topic)
    verdict = verdict.strip()
    # Normalize common forms
    if verdict.lower() in {"dont know", "don't know", "idk"}:
        verdict = "Don't Know"
    else:
        verdict = verdict.title() if verdict.lower() != "don't know" else "Don't Know"

    data = load_memory()
    if topic:
        weak = [t for t in data["weak_topics"] if t.casefold() != topic.casefold()]
        strong = [t for t in data["strong_topics"] if t.casefold() != topic.casefold()]

        if verdict == "Correct":
            strong.insert(0, topic)
        elif verdict in {"Partial", "Incorrect", "Don't Know"}:
            weak.insert(0, topic)

        data["weak_topics"] = _dedupe_keep_order(weak)[:20]
        data["strong_topics"] = _dedupe_keep_order(strong)[:20]
        data["recent_quizzes"] = (
            [
                {
                    "topic": topic,
                    "verdict": verdict,
                    "points": points,
                    "at": date.today().isoformat(),
                }
            ]
            + list(data.get("recent_quizzes", []))
        )[:20]

    data["score"] = int(data.get("score", 0)) + int(points)
    data["high_score"] = max(int(data.get("high_score", 0)), data["score"])
    save_memory(data)
    return data["score"]


def add_note(note: str) -> None:
    note = note.strip()
    if not note:
        return
    data = load_memory()
    notes = [n for n in data["notes"] if n.casefold() != note.casefold()]
    notes.insert(0, note)
    data["notes"] = notes[:20]
    save_memory(data)


def parse_verdict(feedback: str) -> str | None:
    match = re.search(
        r"Verdict:\s*(Correct|Partial|Incorrect|Don't Know|Dont Know)",
        feedback,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1).strip()
    if value.lower() in {"dont know", "don't know"}:
        return "Don't Know"
    return value.title()


def pick_practice_topic() -> str | None:
    """Pick a weak topic to practice. Prefers least-recently-quizzed weak topics."""
    data = load_memory()
    weak = list(data.get("weak_topics") or [])
    if not weak:
        return None

    recent = data.get("recent_quizzes") or []
    last_seen: dict[str, int] = {}
    for idx, item in enumerate(recent):
        topic = str(item.get("topic", "")).casefold()
        if topic and topic not in last_seen:
            last_seen[topic] = idx

    ranked = sorted(
        weak,
        key=lambda t: (last_seen.get(t.casefold(), 10_000), random.random()),
        reverse=True,
    )
    return ranked[0]


def memory_as_prompt() -> str:
    data = load_memory()
    weak = ", ".join(data["weak_topics"][:8]) or "none yet"
    strong = ", ".join(data["strong_topics"][:8]) or "none yet"
    notes = "; ".join(data["notes"][:5]) or "none"
    recent = data["recent_quizzes"][:5]
    if recent:
        recent_txt = "; ".join(
            f"{item['topic']} ({item['verdict']})" for item in recent
        )
    else:
        recent_txt = "none yet"

    return (
        f"- Score: {data.get('score', 0)} (high: {data.get('high_score', 0)})\n"
        f"- Weak topics: {weak}\n"
        f"- Strong topics: {strong}\n"
        f"- Recent quizzes: {recent_txt}\n"
        f"- Notes: {notes}\n"
        "Use this to tailor explanations and suggest practice on weak topics when relevant."
    )


def memory_as_display() -> str:
    data = load_memory()
    lines = ["Student memory:"]
    lines.append(f"Score: {data.get('score', 0)} (high score: {data.get('high_score', 0)})")
    lines.append(
        "Weak: " + (", ".join(data["weak_topics"]) if data["weak_topics"] else "(none)")
    )
    lines.append(
        "Strong: "
        + (", ".join(data["strong_topics"]) if data["strong_topics"] else "(none)")
    )
    if data["recent_quizzes"]:
        lines.append("Recent quizzes:")
        for item in data["recent_quizzes"][:10]:
            pts = item.get("points")
            pts_txt = f", {pts:+d}" if pts is not None else ""
            lines.append(
                f"  - {item['at']}: {item['topic']} -> {item['verdict']}{pts_txt}"
            )
    else:
        lines.append("Recent quizzes: (none)")
    if data["notes"]:
        lines.append("Notes:")
        for note in data["notes"][:10]:
            lines.append(f"  - {note}")
    else:
        lines.append("Notes: (none)")
    return "\n".join(lines)
