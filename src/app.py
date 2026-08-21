import re
from pathlib import Path

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from agents.agent import app
from memory import (
    add_note,
    add_quiz_result,
    clear_memory,
    get_score,
    memory_as_display,
    pick_practice_topic,
    reset_score,
)
from quiz import (
    POINTS_CORRECT,
    POINTS_DONT_KNOW,
    POINTS_INCORRECT,
    POINTS_PARTIAL,
    ask_quiz_question,
    help_me_study,
    parse_quiz_topic,
    pick_random_topic,
    resolve_quiz_turn,
)

st.set_page_config(page_title="QC Study Agent", layout="wide")
st.title("QC Study Agent")
st.caption("Chat · quiz game with points · practice weak topics")


def _init_state() -> None:
    defaults = {
        "messages": [],
        "thread_id": "ui-session-1",
        "lecture_filter": None,
        "pending_quiz": None,
        "show_memory_panel": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _append(role: str, content: str) -> None:
    st.session_state.messages.append({"role": role, "content": content})


def _last_ai_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


def _start_quiz(topic: str, lecture_number: int | None) -> None:
    quiz = ask_quiz_question(topic, lecture_number=lecture_number)
    if str(quiz["question"]).startswith("NOT_ENOUGH_CONTEXT"):
        _append("assistant", "Not enough lecture context for that topic. Try another.")
        st.session_state.pending_quiz = None
        return

    st.session_state.pending_quiz = quiz
    scope = (
        f"lecture {quiz['lecture_number']}"
        if quiz.get("lecture_number") is not None
        else "all lectures"
    )
    _append(
        "assistant",
        f"Quiz ({quiz['topic']} | {scope})\n\n{quiz['question']}\n\n"
        "(Type your answer, `I don't know` to reveal the answer, or `skip`.)",
    )


def _handle_remember(note: str) -> str:
    add_note(note)
    struggle = re.match(
        r"^(?:i\s+)?(?:struggle|struggling)\s+with\s+(.+)$",
        note,
        flags=re.IGNORECASE,
    )
    if struggle:
        add_quiz_result(topic=struggle.group(1).strip(), verdict="Incorrect")
    return f"Remembered: {note}"


def _chat(prompt: str) -> None:
    _append("user", prompt)

    # Active quiz: next message is the answer
    if st.session_state.pending_quiz is not None:
        if prompt.lower().strip() in {"skip", "cancel"}:
            st.session_state.pending_quiz = None
            _append("assistant", "Quiz cancelled (no score change).")
            return

        quiz = st.session_state.pending_quiz
        topic = str(quiz["topic"])
        result = resolve_quiz_turn(
            str(quiz["question"]),
            prompt,
            str(quiz["context"]),
            topic,
        )
        st.session_state.pending_quiz = None
        tip = ""
        if result["verdict"] in {"Partial", "Incorrect", "Don't Know"}:
            tip = "\n\nTip: click **Practice weak topic** to keep drilling."
        _append("assistant", result["feedback"] + tip)
        return

    quiz_req = parse_quiz_topic(prompt)
    if quiz_req is not None:
        topic, quiz_lecture = quiz_req
        lecture = quiz_lecture if quiz_lecture is not None else st.session_state.lecture_filter
        _start_quiz(topic, lecture)
        return

    if prompt.lower().strip() in {
        "practice",
        "practice weak",
        "practice weak topics",
        "quiz my weak topics",
        "drill",
    }:
        topic = pick_practice_topic()
        if topic is None:
            _append(
                "assistant",
                "No weak topics yet. Take a quiz first, or remember: "
                "`I struggle with <topic>`.",
            )
        else:
            _start_quiz(topic, st.session_state.lecture_filter)
        return

    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    with st.spinner("Thinking..."):
        result = app.invoke(
            {
                "messages": [HumanMessage(content=prompt)],
                "context": "",
                "lecture_number": st.session_state.lecture_filter,
            },
            config=config,
        )
    _append("assistant", _last_ai_text(result["messages"]))


_init_state()

# ---- Sidebar ----
with st.sidebar:
    st.header("Controls")
    st.metric("Score", get_score())
    st.caption(
        f"Scoring: Correct {POINTS_CORRECT:+d} | Partial {POINTS_PARTIAL:+d} | "
        f"Incorrect {POINTS_INCORRECT:+d} | Don't know {POINTS_DONT_KNOW:+d}"
    )

    use_filter = st.checkbox(
        "Filter by lecture",
        value=st.session_state.lecture_filter is not None,
    )
    if use_filter:
        st.session_state.lecture_filter = st.number_input(
            "Lecture number",
            min_value=1,
            max_value=31,
            value=int(st.session_state.lecture_filter or 1),
            step=1,
        )
    else:
        st.session_state.lecture_filter = None

    st.session_state.thread_id = st.text_input(
        "Thread id (chat memory)",
        value=st.session_state.thread_id,
    )

    st.divider()
    st.subheader("Study")

    study_topic = st.text_input("Topic", placeholder="e.g. entanglement")

    if st.button("Help me study", use_container_width=True):
        topic = study_topic.strip() or pick_random_topic(st.session_state.lecture_filter)
        _append("user", f"Help me study: {topic}")
        with st.spinner("Preparing a study guide..."):
            lesson = help_me_study(topic, st.session_state.lecture_filter)
        _append("assistant", lesson)
        st.rerun()

    if st.button("Start quiz", use_container_width=True):
        topic = study_topic.strip()
        if not topic:
            st.warning("Enter a topic first, or use Random.")
        else:
            _start_quiz(topic, st.session_state.lecture_filter)
            st.rerun()

    if st.button("Random quiz", use_container_width=True):
        topic = pick_random_topic(st.session_state.lecture_filter)
        _append("assistant", f"Random topic: **{topic}**")
        _start_quiz(topic, st.session_state.lecture_filter)
        st.rerun()

    if st.button("Practice weak topic", use_container_width=True):
        topic = pick_practice_topic()
        if topic is None:
            _append(
                "assistant",
                "No weak topics yet. Take a quiz first, or remember a struggle note.",
            )
        else:
            _start_quiz(topic, st.session_state.lecture_filter)
        st.rerun()

    if st.session_state.pending_quiz is not None:
        if st.button("Cancel quiz", use_container_width=True):
            st.session_state.pending_quiz = None
            _append("assistant", "Quiz cancelled.")
            st.rerun()

    st.divider()
    st.subheader("Memory")

    remember_text = st.text_input(
        "Remember note",
        placeholder="I struggle with Bloch sphere",
    )
    if st.button("Save note", use_container_width=True) and remember_text.strip():
        msg = _handle_remember(remember_text.strip())
        _append("assistant", msg)
        st.rerun()

    if st.button("Show memory", use_container_width=True):
        st.session_state.show_memory_panel = True
        _append("assistant", memory_as_display())
        st.rerun()

    if st.button("Clear memory", use_container_width=True):
        clear_memory()
        _append("assistant", "Cleared student memory.")
        st.rerun()

    if st.button("Reset score", use_container_width=True):
        reset_score()
        _append("assistant", "Score reset to 0.")
        st.rerun()

    if st.button("Clear chat display", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.caption(f"Project: {Path(__file__).resolve().parents[1].name}")

# ---- Status ----
if st.session_state.pending_quiz is not None:
    st.info(
        f"Quiz in progress on **{st.session_state.pending_quiz['topic']}** — "
        "answer for points, or type **I don't know** to see the answer."
    )
elif st.session_state.lecture_filter is not None:
    st.info(f"Lecture filter: **{st.session_state.lecture_filter}**")

if st.session_state.show_memory_panel:
    with st.expander("Student memory", expanded=True):
        st.text(memory_as_display())

# ---- Chat history ----
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ---- Input ----
placeholder = (
    "Your quiz answer..."
    if st.session_state.pending_quiz is not None
    else "Ask about the lectures, or: quiz me on entanglement"
)
prompt = st.chat_input(placeholder)
if prompt and prompt.strip():
    _chat(prompt.strip())
    st.rerun()
