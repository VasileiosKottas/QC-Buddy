import argparse
import re
import sys

from langchain_core.messages import AIMessage, HumanMessage

from agents.agent import app
from ingest.ingest import ingest_all_lectures
from quiz import ask_quiz_question, parse_quiz_topic, resolve_quiz_turn
from memory import (
    add_note,
    add_quiz_result,
    clear_memory,
    get_score,
    memory_as_display,
    pick_practice_topic,
    reset_score,
)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="QC lecture RAG tools")
    parser.add_argument(
        "command",
        choices=["ingest", "ask", "chat"],
        help="ingest lectures, ask one question, or start a chat loop",
    )
    parser.add_argument(
        "--question",
        default="What quotes does Shor use about how weird quantum theory is?",
        help="Question to ask when using the ask command",
    )
    parser.add_argument(
        "--thread-id",
        default="study-session-1",
        help="Conversation thread id for memory",
    )
    parser.add_argument(
        "--lecture",
        type=int,
        default=None,
        help="Optional lecture number filter for ask/chat",
    )
    args = parser.parse_args()

    if args.command == "ingest":
        ingest_all_lectures()
        return

    config = {"configurable": {"thread_id": args.thread_id}}
    lecture_filter = args.lecture

    if args.command == "ask":
        result = app.invoke(
            {
                "messages": [HumanMessage(content=args.question)],
                "context": "",
                "lecture_number": lecture_filter,
            },
            config=config,
        )
        print(_last_ai_text(result["messages"]))
        return

    print("QC study chat (type 'exit' to quit)")
    print("Quiz: 'quiz me on <topic>' or 'quiz me on <topic> in lecture 9'")
    print("Practice: 'practice' / 'practice weak' (uses weak topics from memory)")
    print("Quiz game: answer for points, or say 'I don't know' to reveal the answer")
    print("Filter: 'use lecture 11' / 'clear lecture filter'")
    print("Memory: 'show memory' / 'clear memory' / 'remember <note>' / 'show score'")
    print(f"Current score: {get_score()}")
    pending_quiz: dict | None = None

    while True:
        user_text = input("\nYou: ").strip()
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            break

        memory_cmd = _handle_memory_command(user_text)
        if memory_cmd is not None:
            print(f"\nAssistant: {memory_cmd}")
            continue

        is_filter_cmd, filter_value = _parse_lecture_filter_command(user_text)
        if is_filter_cmd:
            lecture_filter = filter_value
            if lecture_filter is None:
                print("\nAssistant: Cleared lecture filter. Searching all lectures.")
            else:
                print(f"\nAssistant: Filtering to lecture {lecture_filter}.")
            continue

        if _is_practice_command(user_text):
            topic = pick_practice_topic()
            if topic is None:
                print(
                    "\nAssistant: No weak topics yet. "
                    "Take a quiz first, or add one with: remember I struggle with <topic>"
                )
                continue
            pending_quiz = _start_quiz(topic, lecture_filter)
            continue

        quiz_req = parse_quiz_topic(user_text)
        if quiz_req is not None:
            topic, quiz_lecture = quiz_req
            effective_lecture = (
                quiz_lecture if quiz_lecture is not None else lecture_filter
            )
            pending_quiz = _start_quiz(topic, effective_lecture)
            continue

        if pending_quiz is not None:
            if user_text.lower() in {"skip", "cancel"}:
                pending_quiz = None
                print("\nAssistant: Quiz cancelled (no score change).")
                continue
            topic = str(pending_quiz["topic"])
            result = resolve_quiz_turn(
                str(pending_quiz["question"]),
                user_text,
                str(pending_quiz["context"]),
                topic,
            )
            pending_quiz = None
            print(f"\nAssistant: {result['feedback']}")
            if result["verdict"] in {"Partial", "Incorrect", "Don't Know"}:
                print("(Tip: type 'practice' to keep drilling weak topics.)")
            continue

        result = app.invoke(
            {
                "messages": [HumanMessage(content=user_text)],
                "context": "",
                "lecture_number": lecture_filter,
            },
            config=config,
        )
        print(f"\nAssistant: {_last_ai_text(result['messages'])}")


def _parse_lecture_filter_command(user_text: str) -> tuple[bool, int | None]:
    """Return (is_filter_command, lecture_number_or_None_to_clear)."""
    text = user_text.strip().lower()
    if text in {"clear lecture filter", "clear filter", "all lectures"}:
        return True, None

    match = re.match(
        r"^(?:use\s+)?(?:lecture|lec)\s*_?\s*(\d+)$",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return True, int(match.group(1))

    return False, None


def _handle_memory_command(user_text: str) -> str | None:
    text = user_text.strip()
    lower = text.lower()
    if lower in {"show memory", "memory"}:
        return memory_as_display()
    if lower in {"show score", "score"}:
        return f"Score: {get_score()}"
    if lower in {"reset score"}:
        reset_score()
        return "Score reset to 0."
    if lower in {"clear memory", "forget memory"}:
        clear_memory()
        return "Cleared student memory."
    match = re.match(r"^remember\s+(.+)$", text, flags=re.IGNORECASE)
    if match:
        note = match.group(1).strip()
        add_note(note)
        # Also treat "I struggle with X" as a weak topic seed.
        struggle = re.match(
            r"^(?:i\s+)?(?:struggle|struggling)\s+with\s+(.+)$",
            note,
            flags=re.IGNORECASE,
        )
        if struggle:
            add_quiz_result(topic=struggle.group(1).strip(), verdict="Incorrect", points=0)
        return f"Remembered: {note}"
    return None


def _is_practice_command(user_text: str) -> bool:
    text = user_text.strip().lower()
    return text in {
        "practice",
        "practice weak",
        "practice weak topics",
        "quiz my weak topics",
        "drill",
    }


def _start_quiz(topic: str, lecture_number: int | None) -> dict | None:
    quiz = ask_quiz_question(topic, lecture_number=lecture_number)
    if str(quiz["question"]).startswith("NOT_ENOUGH_CONTEXT"):
        print("\nAssistant: Not enough lecture context for that topic. Try another.")
        return None

    scope = (
        f"lecture {quiz['lecture_number']}"
        if quiz.get("lecture_number") is not None
        else "all lectures"
    )
    print(f"\nAssistant: Quiz ({quiz['topic']} | {scope})")
    print(quiz["question"])
    print("(Type your answer, 'I don't know' to reveal, or 'skip' to cancel.)")
    return quiz


def _last_ai_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


if __name__ == "__main__":
    main()
