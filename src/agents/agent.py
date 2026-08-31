from pathlib import Path
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from rag import format_docs, parse_lecture_mention, retrieve_docs
from memory import memory_as_prompt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_DB = PROJECT_ROOT / "data" / "checkpoints.sqlite"

REWRITE_PROMPT = """Given the conversation, rewrite the latest user message as a standalone
search query for lecture notes. Keep key technical terms. Return ONLY the query.
Do not include phrases like "lecture 11" unless they are part of the technical topic.

Conversation:
{history}

Latest user message: {question}
"""

ANSWER_PROMPT = """You are a quantum computing study assistant.
Answer the student's latest message using the lecture context and conversation history.
If the context is insufficient, say you don't know rather than inventing.

When you write math, use ONLY Streamlit-safe KaTeX:
- inline: $...$
- display: $$...$$ on their own lines
- one equation per $$...$$ block
Prefer standard QC notation (|0\\rangle, \\otimes, 1/\\sqrt 2, H|0\\rangle).
FORBIDDEN (breaks rendering): align, align*, equation, equation*, &=, any begin/end environment, \\left, \\right.
Do not invent equations that are not supported by the notes.
Do not wrap the whole answer in a markdown code fence.

Lecture context:
{context}

At the end, cite lecture files used like:
Resources: Lecture_XX.pdf
"""


class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    context: str
    lecture_number: NotRequired[int | None]


def _text(message: BaseMessage) -> str:
    content = message.content
    return content if isinstance(content, str) else str(content)


def _latest_user_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return _text(message)
    return ""


def _format_history(messages: list[BaseMessage], limit: int = 6) -> str:
    lines = []
    for message in messages[-limit:]:
        role = "user" if isinstance(message, HumanMessage) else "assistant"
        if isinstance(message, (HumanMessage, AIMessage)):
            lines.append(f"{role}: {_text(message)}")
    return "\n".join(lines)


def _standalone_query(messages: list[BaseMessage]) -> str:
    question = _latest_user_text(messages)
    cleaned, _ = parse_lecture_mention(question)
    question = cleaned or question

    prior = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))][:-1]
    if not prior:
        return question

    llm = ChatOllama(model="llama3.2", temperature=0)
    rewritten = llm.invoke(
        [
            HumanMessage(
                content=REWRITE_PROMPT.format(
                    history=_format_history(prior),
                    question=question,
                )
            )
        ]
    )
    query = _text(rewritten).strip().strip('"')
    return query or question


def retrieve(state: State) -> dict:
    latest = _latest_user_text(state["messages"])
    _, mentioned_lecture = parse_lecture_mention(latest)
    lecture_number = (
        mentioned_lecture
        if mentioned_lecture is not None
        else state.get("lecture_number")
    )

    query = _standalone_query(state["messages"])
    docs = retrieve_docs(query, lecture_number=lecture_number, k=4)
    return {"context": format_docs(docs)}


def generate(state: State) -> dict:
    system = (
        ANSWER_PROMPT.format(context=state.get("context", ""))
        + "\n\nStudent memory:\n"
        + memory_as_prompt()
    )
    llm = ChatOllama(model="llama3.2", temperature=0)
    response = llm.invoke(
        [
            SystemMessage(content=system),
            *state["messages"],
        ]
    )
    return {"messages": [AIMessage(content=response.content)]}


def build_app():
    graph = StateGraph(State)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3

    conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return graph.compile(checkpointer=checkpointer)


app = build_app()
