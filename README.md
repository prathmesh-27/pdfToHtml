# PDF to HTML Studio

Full-stack local application: FastAPI backend + React/Vite frontend.

## Start backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
API docs: http://127.0.0.1:8000/docs

## Start frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173.

## REST API
- `POST /api/v1/documents/convert` — multipart field `file`; query `include_html=true|false`, `render_page_background=true|false`.
- `GET /api/v1/documents/{document_id}` — document summary.
- `GET /api/v1/documents/{document_id}/json` — complete JSON with all page HTML.
- `GET /api/v1/documents/{document_id}/pages/{page_number}` — one page JSON, HTML string and metadata (1-based).
- `GET /api/v1/documents/{document_id}/pages/{page_number}/html` — raw HTML response.
- `GET /api/v1/documents/{document_id}/assets/{filename}` — extracted image.
- `DELETE /api/v1/documents/{document_id}` — delete document.

SQLite and files are stored under `backend/data`. This is a functional local starter, not a hardened public multi-tenant service. Add authentication, ownership checks, upload limits, rate limits, malware scanning, retention and background workers before public deployment. PDF is fixed-layout; exact HTML fidelity is not guaranteed. Fonts are not embedded and vector artwork/table reconstruction may need extra processing. Page-background rendering is available for visual preservation, with reduced editability.
