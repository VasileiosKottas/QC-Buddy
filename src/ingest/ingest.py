import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LECTURES_DIR = PROJECT_ROOT / "data" / "peter_shor_lectures_fall_2022"
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def list_lecture_pdfs(lectures_dir: Path | None = None) -> list[Path]:
    directory = lectures_dir or LECTURES_DIR
    return sorted(directory.glob("Lecture_*.pdf"))


def _lecture_number(pdf_path: Path) -> int:
    match = re.search(r"Lecture_(\d+)", pdf_path.stem, re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not parse lecture number from {pdf_path.name}")
    return int(match.group(1))


def load_lecture(pdf_path: Path | str) -> list[Document]:
    path = Path(pdf_path)
    pages = PyPDFLoader(str(path)).load()
    lecture_number = _lecture_number(path)

    for page in pages:
        lines = page.page_content.split("\n")
        if len(lines) > 1:
            page.page_content = "\n".join(lines[1:]).strip()
        page.metadata = {
            "source": path.name,
            "source_path": str(path),
            "page": page.metadata.get("page", 0),
            "lecture_number": lecture_number,
        }
    return pages


def ingest_lectures(pdf_paths: list[Path | str]) -> list[Document]:
    all_pages: list[Document] = []
    for pdf_path in pdf_paths:
        pages = load_lecture(pdf_path)
        all_pages.extend(pages)
        print(f"Loaded {Path(pdf_path).name}: {len(pages)} pages")
    return all_pages


def split_docs(pages: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(pages)


def embed_store_in_chroma(
    docs: list[Document],
    persist_directory: Path | str | None = None,
) -> Chroma:
    persist_directory = Path(persist_directory or CHROMA_DIR)
    persist_directory.mkdir(parents=True, exist_ok=True)

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=str(persist_directory),
    )


def ingest_all_lectures(
    lectures_dir: Path | str | None = None,
    persist_directory: Path | str | None = None,
) -> Chroma:
    pdf_paths = list_lecture_pdfs(Path(lectures_dir) if lectures_dir else None)
    if not pdf_paths:
        raise FileNotFoundError(f"No Lecture_*.pdf files found in {lectures_dir or LECTURES_DIR}")

    print(f"Found {len(pdf_paths)} lecture PDFs")
    pages = ingest_lectures(pdf_paths)
    docs = split_docs(pages)
    print(f"Split into {len(docs)} chunks")

    db = embed_store_in_chroma(docs, persist_directory=persist_directory)
    print(f"Stored {db._collection.count()} vectors in {persist_directory or CHROMA_DIR}")
    return db


if __name__ == "__main__":
    ingest_all_lectures()
