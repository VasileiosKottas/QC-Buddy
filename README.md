# QC Buddy

A local study buddy for quantum computing. It reads your lecture notes, answers questions from them, remembers what you struggle with, and can quiz you like a small game.

Built with RAG + LangGraph + a Streamlit UI. Runs locally with Ollama.

## New computer / Cursor handoff

**Read [CONTINUE.md](CONTINUE.md)** — full clone → setup → ingest → run checklist, project map, and known quirks.

## Quick start

1. Clone this repo and open it in Cursor  
2. Create a venv and install deps (`pip install -r requirements.txt`)  
3. Install [Ollama](https://ollama.com) and run `ollama pull llama3.2`  
4. Download lectures from [Shor’s notes](https://math.mit.edu/~shor/435-LN/) into `data/peter_shor_lectures_fall_2022/`  
5. Ingest and run:

```powershell
.\venv\Scripts\python.exe src/main.py ingest
.\venv\Scripts\python.exe -m streamlit run src/app.py
```

If PowerShell blocks `activate`, skip it and use `.\venv\Scripts\python.exe` as above.

## What you can do

- ask questions about the notes  
- `quiz me on entanglement` / **Help me study** / **Random quiz**  
- `practice` — drills a weak topic  
- `I don't know` during a quiz to see the answer (costs points)  
- `use lecture 11` / `clear lecture filter`  
- `show memory` / `show score`  

Scoring: correct +10, partial +3, wrong −5, don’t know −3.

## Notes

PDFs, Chroma DB, chat checkpoints, and student memory stay on your machine (gitignored). Re-run ingest when you add lectures.
