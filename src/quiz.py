import random
import re

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

from memory import add_quiz_result, parse_verdict, pick_practice_topic
from rag import parse_lecture_mention, retrieve_context

# Game scoring
POINTS_CORRECT = 10
POINTS_PARTIAL = 3
POINTS_INCORRECT = -5
POINTS_DONT_KNOW = -3

# Kept as a plain string; examples avoid { } so str.format() is safe.
LATEX_MATH_RULES = (
    "When you write math, use ONLY Streamlit-safe KaTeX:\n"
    "- inline: $...$\n"
    "- display: $$...$$ on their own lines\n"
    "- one equation per $$...$$ block\n"
    r"Prefer standard QC notation (|0\rangle, \otimes, 1/\sqrt 2, H|0\rangle)." "\n"
    "FORBIDDEN (breaks rendering): align, align*, equation, equation*, &=, "
    "any begin/end environment, \\left, \\right.\n"
    "Do not invent equations that are not supported by the notes.\n"
    "Do not wrap the whole answer in a markdown code fence."
)

# Topics that appear across Shor-style QC notes (used for Random)
STUDY_TOPICS = [
    "quantum weirdness and history of quantum mechanics",
    "qubits and superposition",
    "measurement in quantum mechanics",
    "Bloch sphere",
    "Hadamard gate",
    "Pauli gates",
    "entanglement",
    "EPR pairs",
    "Bell's theorem",
    "no-cloning theorem",
    "quantum teleportation",
    "dense coding",
    "quantum circuits",
    "unitary operations",
    "Deutsch algorithm",
    "Grover search",
    "Shor's algorithm",
    "quantum Fourier transform",
    "phase estimation",
    "quantum error correction",
]

STUDY_PROMPT = """You are a tutor helping a student study quantum computing.
Using ONLY the lecture context below, teach the topic clearly.

Topic: {topic}

Rules:
- Explain in plain language first, then add a bit more rigor
- Use short paragraphs and bullet points where helpful
- Stay grounded in the notes; if something is missing, say so
- End with 2 quick self-check questions (do NOT answer them)
- Cite lecture files like: Resources: Lecture_XX.pdf

""" + LATEX_MATH_RULES + """

Context:
{context}
"""

GENERATE_PROMPT = """Using ONLY the lecture context below, write ONE short quiz question
to test understanding of the topic: {topic}

Rules:
- Do NOT answer the question
- Prefer conceptual understanding over trivia
- Keep it to 1-3 sentences
- If the context is too weak, say: NOT_ENOUGH_CONTEXT
- If the question needs math, write it in LaTeX ($...$ or $$...$$)

Context:
{context}
"""

GRADE_PROMPT = """Grade the student's answer using ONLY the lecture context.

Reply in this exact format:
Verdict: Correct | Partial | Incorrect
Explanation: 2-4 sentences grounded in the notes
Correct answer: a clear short answer from the notes
Resources: Lecture_XX.pdf

""" + LATEX_MATH_RULES + """

Question: {question}
Student answer: {answer}

Lecture context:
{context}
"""

REVEAL_PROMPT = """The student said they don't know. Using ONLY the lecture context,
explain the correct answer clearly and briefly (3-6 sentences).

Reply in this exact format:
Verdict: Don't Know
Explanation: teach the answer from the notes in simple language
Correct answer: one short summary sentence
Resources: Lecture_XX.pdf

""" + LATEX_MATH_RULES + """

Question: {question}

Lecture context:
{context}
"""


def retrieve_notes(
    topic: str,
    k: int = 4,
    lecture_number: int | None = None,
) -> str:
    return retrieve_context(
        f"quiz topic: {topic}",
        lecture_number=lecture_number,
        k=k,
    )


def ask_quiz_question(
    topic: str,
    lecture_number: int | None = None,
) -> dict[str, str | int | None]:
    cleaned_topic, parsed_lecture = parse_lecture_mention(topic)
    lecture_number = parsed_lecture if parsed_lecture is not None else lecture_number
    topic = cleaned_topic or topic

    context = retrieve_notes(topic, lecture_number=lecture_number)
    llm = ChatOllama(model="llama3.2", temperature=0)
    response = llm.invoke(
        [HumanMessage(content=GENERATE_PROMPT.format(topic=topic, context=context))]
    )
    question = response.content if isinstance(response.content, str) else str(response.content)
    return {
        "question": question.strip(),
        "context": context,
        "topic": topic,
        "lecture_number": lecture_number,
    }


def pick_random_topic(lecture_number: int | None = None) -> str:
    """Pick a random study/quiz topic. Prefers weak topics sometimes."""
    weak = pick_practice_topic()
    if weak and random.random() < 0.35:
        return weak
    if lecture_number is not None:
        return f"key ideas from lecture {lecture_number}"
    return random.choice(STUDY_TOPICS)


def help_me_study(topic: str, lecture_number: int | None = None) -> str:
    """Explain a topic from the notes (no scoring)."""
    cleaned_topic, parsed_lecture = parse_lecture_mention(topic)
    lecture_number = parsed_lecture if parsed_lecture is not None else lecture_number
    topic = cleaned_topic or topic

    context = retrieve_notes(topic, lecture_number=lecture_number)
    if not context.strip():
        return "I couldn't find enough notes for that topic."

    llm = ChatOllama(model="llama3.2", temperature=0.2)
    response = llm.invoke(
        [HumanMessage(content=STUDY_PROMPT.format(topic=topic, context=context))]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content.strip()


def is_dont_know(answer: str) -> bool:
    text = answer.strip().lower()
    patterns = [
        r"^i\s*don'?t\s*know\.?$",
        r"^dont\s*know\.?$",
        r"^don'?t\s*know\.?$",
        r"^idk\.?$",
        r"^no\s*idea\.?$",
        r"^not\s*sure\.?$",
        r"^give\s*up\.?$",
        r"^reveal\.?$",
        r"^show\s*(me\s*)?(the\s*)?answer\.?$",
    ]
    return any(re.match(p, text) for p in patterns)


def points_for_verdict(verdict: str) -> int:
    mapping = {
        "Correct": POINTS_CORRECT,
        "Partial": POINTS_PARTIAL,
        "Incorrect": POINTS_INCORRECT,
        "Don't Know": POINTS_DONT_KNOW,
    }
    return mapping.get(verdict, 0)


def grade_answer(question: str, answer: str, context: str) -> str:
    llm = ChatOllama(model="llama3.2", temperature=0)
    response = llm.invoke(
        [
            HumanMessage(
                content=GRADE_PROMPT.format(
                    question=question,
                    answer=answer,
                    context=context,
                )
            )
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content.strip()


def reveal_answer(question: str, context: str) -> str:
    llm = ChatOllama(model="llama3.2", temperature=0)
    response = llm.invoke(
        [
            HumanMessage(
                content=REVEAL_PROMPT.format(question=question, context=context)
            )
        ]
    )
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content.strip()


def resolve_quiz_turn(question: str, answer: str, context: str, topic: str) -> dict:
    """
    Grade or reveal, apply score, return display text + metadata.
    """
    if is_dont_know(answer):
        feedback = reveal_answer(question, context)
        verdict = "Don't Know"
        points = POINTS_DONT_KNOW
    else:
        feedback = grade_answer(question, answer, context)
        verdict = parse_verdict(feedback) or "Incorrect"
        points = points_for_verdict(verdict)

    total = add_quiz_result(topic=topic, verdict=verdict, points=points)
    sign = "+" if points >= 0 else ""
    scoreboard = (
        f"\n\n---\nPoints this turn: {sign}{points}\n"
        f"Total score: {total}\n"
        f"(Correct {POINTS_CORRECT:+d} | Partial {POINTS_PARTIAL:+d} | "
        f"Incorrect {POINTS_INCORRECT:+d} | Don't know {POINTS_DONT_KNOW:+d})"
    )
    return {
        "feedback": feedback + scoreboard,
        "verdict": verdict,
        "points": points,
        "score": total,
    }


def parse_quiz_topic(user_text: str) -> tuple[str, int | None] | None:
    """
    Return (topic, lecture_number) if message is a quiz request, else None.
    Examples:
      quiz me on entanglement
      quiz me on Hadamard in lecture 9
      quiz lecture 11 on Bell
    """
    text = user_text.strip()
    patterns = [
        r"^quiz\s+me\s+on\s+(.+)$",
        r"^quiz\s+me\s+about\s+(.+)$",
        r"^quiz\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, text, flags=re.IGNORECASE)
        if match:
            raw = match.group(1).strip().rstrip("?.!")
            if not raw:
                return None
            topic, lecture_number = parse_lecture_mention(raw)
            on_match = re.match(
                r"^on\s+(.+)$",
                topic,
                flags=re.IGNORECASE,
            )
            if on_match and lecture_number is not None:
                topic = on_match.group(1).strip()
            if topic:
                return topic, lecture_number
    return None
