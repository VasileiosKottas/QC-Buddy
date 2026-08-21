import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import ChatOllama

from ingest.ingest import CHROMA_DIR, EMBEDDING_MODEL

TEMPLATE = """Answer the question using ONLY the context below.
If the answer is not in the context, say you don't know.

Context:
{context}

Question: {question}

At the end of the response, list the lecture file(s) you used in this format:
Resources: Lecture_XX.pdf
"""

_embeddings = None
_db = None


def _get_db() -> Chroma:
    global _embeddings, _db
    if _db is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        _db = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=_embeddings,
        )
    return _db


def format_docs(docs: list[Document]) -> str:
    parts = []
    for doc in docs:
        source = Path(str(doc.metadata.get("source", "unknown"))).name
        page = doc.metadata.get("page", "?")
        lecture = doc.metadata.get("lecture_number", "?")
        parts.append(
            f"[source: {source}, lecture: {lecture}, page: {page}]\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(parts)


def parse_lecture_mention(text: str) -> tuple[str, int | None]:
    """
    Extract an optional lecture number from text and return (cleaned_text, lecture_number).
    Supports: 'lecture 11', 'lec 11', 'Lecture_11'
    """
    pattern = re.compile(
        r"\b(?:from\s+|in\s+|only\s+)?(?:lecture|lec)\s*_?\s*(\d+)\b",
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    if not match:
        return text.strip(), None

    lecture_number = int(match.group(1))
    cleaned = (text[: match.start()] + text[match.end() :]).strip(" ,.-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, lecture_number


def retrieve_docs(
    query: str,
    *,
    lecture_number: int | None = None,
    k: int = 4,
    fetch_k: int = 20,
    search_type: str = "mmr",
) -> list[Document]:
    """Shared retrieval with optional lecture metadata filter + MMR."""
    db = _get_db()
    search_kwargs: dict = {"k": k}
    if lecture_number is not None:
        search_kwargs["filter"] = {"lecture_number": lecture_number}

    if search_type == "mmr":
        search_kwargs["fetch_k"] = max(fetch_k, k)
        retriever = db.as_retriever(search_type="mmr", search_kwargs=search_kwargs)
        return retriever.invoke(query)

    return db.similarity_search(
        query,
        k=k,
        filter=search_kwargs.get("filter"),
    )


def retrieve_context(
    query: str,
    *,
    lecture_number: int | None = None,
    k: int = 4,
) -> str:
    docs = retrieve_docs(query, lecture_number=lecture_number, k=k)
    return format_docs(docs)


def ask_question(question: str, lecture_number: int | None = None) -> str:
    cleaned, parsed_lecture = parse_lecture_mention(question)
    lecture_number = parsed_lecture if parsed_lecture is not None else lecture_number

    prompt = PromptTemplate.from_template(TEMPLATE)
    llm = ChatOllama(model="llama3.2", temperature=0)
    context = retrieve_context(cleaned or question, lecture_number=lecture_number, k=4)
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"question": cleaned or question, "context": context})
