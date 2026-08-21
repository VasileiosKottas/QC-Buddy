# QC Buddy

A local study buddy for quantum computing. It reads your lecture notes, answers questions from them, remembers what you struggle with, and can quiz you like a small game.

Built with RAG + LangGraph + a Streamlit UI. Runs locally with Ollama.

## Get the lectures

The PDFs are not in this repo. Grab Peter Shor's notes from here:

[https://math.mit.edu/~shor/435-LN/](https://math.mit.edu/~shor/435-LN/)

Drop them into:

```text
data/peter_shor_lectures_fall_2022/
```

Name them like `Lecture_01.pdf`, `Lecture_02.pdf`, … (or keep whatever names you download and adjust paths if needed).

## Setup

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

You'll also want [Ollama](https://ollama.com) with a chat model:

```powershell
ollama pull llama3.2
```

Then build the vector store from the PDFs:

```powershell
python src/main.py ingest
```

## Run it

Chat in the terminal:

```powershell
python src/main.py chat
```

Or open the UI:

```powershell
streamlit run src/app.py
```

## What you can do

In chat (or the UI):

- ask questions about the notes
- `quiz me on entanglement`
- `practice` — drills a weak topic
- say `I don't know` during a quiz to see the answer (costs points)
- `use lecture 11` / `clear lecture filter`
- `show memory` / `show score`

Scoring is roughly: correct +10, partial +3, wrong −5, don't know −3.

## Notes

Your Chroma DB, chat checkpoints, and student memory stay on your machine (they're gitignored). Re-run ingest whenever you add more lectures.
