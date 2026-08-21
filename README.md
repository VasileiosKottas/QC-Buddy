# QC Buddy

Local study agent for quantum computing notes: RAG over lecture PDFs, LangGraph chat with memory, quiz game with points, and a Streamlit UI.

## Features

- **RAG Q&A** grounded in your lecture notes (Chroma + local embeddings)
- **LangGraph chat** with persistent thread memory
- **Quiz / practice** with scoring (`+10` correct, `-5` incorrect, `-3` for "I don't know" + answer reveal)
- **Student memory** (weak/strong topics, score)
- **Streamlit UI** for chat, study, and quiz

## Setup

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

Install [Ollama](https://ollama.com) and pull a model:

```powershell
ollama pull llama3.2
```

Put lecture PDFs in:

```text
data/peter_shor_lectures_fall_2022/Lecture_XX.pdf
```

Then ingest:

```powershell
python src/main.py ingest
```

## Run

CLI chat:

```powershell
python src/main.py chat
```

Streamlit UI:

```powershell
streamlit run src/app.py
```

## Useful commands (chat)

- `quiz me on entanglement`
- `practice` — quiz a weak topic
- `I don't know` — reveal answer (costs points)
- `use lecture 11` / `clear lecture filter`
- `show memory` / `show score`

## Notes

- Vector DB, checkpoints, and student memory are local (gitignored) and created on first use.
- Lecture PDFs are gitignored; add your own notes before ingesting.
