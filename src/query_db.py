from langchain_core.documents import Document

from rag import retrieve_docs


def query_db(
    query: str,
    k: int = 3,
    lecture_number: int | None = None,
) -> list[Document]:
    return retrieve_docs(query, lecture_number=lecture_number, k=k)
