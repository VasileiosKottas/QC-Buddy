# Continue QC Buddy on another computer (Cursor)

This is the handoff guide. Clone the repo, follow these steps once, then keep building in Cursor.

Repo: https://github.com/VasileiosKottas/QC-Buddy

---

## 1. Get the code

```powershell
git clone https://github.com/VasileiosKottas/QC-Buddy.git
cd QC-Buddy
```

Open the folder in **Cursor** (`File → Open Folder`).

---

## 2. Python environment

Needs **Python 3.11+** (3.12 is fine).

### Windows

```powershell
python -m venv venv
```

If PowerShell blocks `activate`:

```powershell
# option A — no activate needed
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# option B — allow scripts for this terminal only
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\activate
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

First install can take a while (`torch` / `sentence-transformers`).

---

## 3. Ollama (local chat model)

1. Install from https://ollama.com  
2. Start Ollama (app or `ollama serve`)  
3. Pull the model this project uses:

```powershell
ollama pull llama3.2
ollama list
```

Check it’s up: open http://localhost:11434 — you should see something like “Ollama is running”.

If chat fails with `WinError 10061` / connection refused → Ollama isn’t running.

---

## 4. Lecture PDFs (not in git)

Download Peter Shor’s notes:

https://math.mit.edu/~shor/435-LN/

Put them here:

```text
data/peter_shor_lectures_fall_2022/Lecture_01.pdf
data/peter_shor_lectures_fall_2022/Lecture_02.pdf
...
```

Filenames should match `Lecture_XX.pdf` so ingest can parse lecture numbers.

---

## 5. Build the vector DB

From the project root:

```powershell
.\venv\Scripts\python.exe src/main.py ingest
```

This creates `data/chroma_db/` locally (gitignored). Re-run after adding/changing PDFs.

---

## 6. Run

**Streamlit UI**

```powershell
.\venv\Scripts\python.exe -m streamlit run src/app.py
```

**CLI chat**

```powershell
.\venv\Scripts\python.exe src/main.py chat
```

Streamlit file-watching is off (see `.streamlit/config.toml`) to avoid noisy `transformers`/`torchvision` errors. After code edits: stop with `Ctrl+C` and start again.

---

## What’s in git vs local-only

| In the repo | Local only (recreate on new machine) |
|-------------|--------------------------------------|
| `src/` code | `venv/` |
| `requirements.txt` | `data/*.pdf` lectures |
| README / this file | `data/chroma_db/` |
| `.streamlit/config.toml` | `data/checkpoints.sqlite*` |
| `.env.example` | `data/student_memory.json` |

Student memory (score, weak topics) does **not** travel with git. That’s intentional.

Optional: copy `.env.example` → `.env` if you later use HF/OpenAI keys. Default path is fully local (Ollama + Hugging Face embeddings).

---

## Project map (where to edit)

```text
src/
  app.py              Streamlit UI
  main.py             CLI: ingest / ask / chat
  rag.py              Chroma load + retrieve + lecture filter
  ingest/ingest.py    PDF → chunks → Chroma
  agents/agent.py     LangGraph chat agent + memory injection
  quiz.py             Quiz, practice, help-me-study, scoring
  memory.py           Student profile JSON (weak/strong/score)
  math_format.py      Sanitize align* LaTeX for Streamlit KaTeX
  query_db.py         Thin search helper
data/
  peter_shor_lectures_fall_2022/   PDFs (you add)
  chroma_db/                       vector store (after ingest)
```

---

## Useful chat / UI commands

- `quiz me on entanglement` / `quiz me on X in lecture 9`
- `practice` — quiz a weak topic
- `I don't know` / `idk` — reveal answer (−3 points)
- `use lecture 11` / `clear lecture filter`
- `show memory` / `show score` / `reset score`
- UI: **Help me study**, **Random quiz**, **Practice weak topic**

Scoring: correct +10, partial +3, incorrect −5, don’t know −3.

---

## Known quirks

1. **PowerShell can’t activate venv** → use `.\venv\Scripts\python.exe -m ...`  
2. **Ollama connection errors** → start Ollama first  
3. **KaTeX red errors** → prompts ban `align*`; `math_format.py` cleans leftovers. Prefer simple `$...$` / `$$...$$`  
4. **PDF math is messy** in retrieval (pypdf). LLM rewrites to LaTeX; better ingest is a future upgrade  
5. **HF download warning** on first embedding load is normal  

---

## Cursor tips on the new machine

1. Open the cloned folder as the workspace root  
2. Select the venv interpreter: `venv\Scripts\python.exe`  
3. Keep terminal cwd at the project root when running ingest/app  
4. Don’t commit `venv/`, PDFs, or `chroma_db/`  

---

## Good next features (if picking up later)

1. **Better equation ingest** — math-aware PDF parsing or a curated `data/equations.md`  
2. **Figures** — extract lecture images, caption them, show relevant ones in Streamlit  
3. **Weak-topic auto-continue** after wrong quiz answers  
4. **Copy student_memory.json** between machines if you want score/weak topics to follow you  

---

## Quick checklist (new PC)

- [ ] Clone repo  
- [ ] Create venv + `pip install -r requirements.txt`  
- [ ] Install Ollama + `ollama pull llama3.2`  
- [ ] Download lectures into `data/peter_shor_lectures_fall_2022/`  
- [ ] `python src/main.py ingest`  
- [ ] `python -m streamlit run src/app.py`  
- [ ] Ask a test question / run a quiz  
