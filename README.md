# Iqra LMS Assistant

AI study assistant: chat, web search with sources, assignment answers, PDF Q&A, MCQ generation.

## Run on Windows (PowerShell)

Backend (Python 3.10+):

    cd backend
    py -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env
    notepad .env
    uvicorn main:app --reload --port 8000

Frontend (Node 18+), in a second terminal:

    cd frontend
    npm install
    npm run dev

Open http://localhost:5173

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` first.
