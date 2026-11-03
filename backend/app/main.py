
import json, re, shutil, sqlite3, tempfile, uuid
from datetime import datetime, timezone
from pathlib import Path
from html import escape
import fitz
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = DATA / "app.sqlite3"
MAX_UPLOAD = 100 * 1024 * 1024

def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, filename TEXT, page_count INTEGER, folder TEXT, created_at TEXT)")
        c.commit()

def safe_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name) or "document.pdf"

def render_page(n, width, height, blocks, bg=None):
    elements = []
    for block in blocks:
        x0,y0,x1,y1 = map(float, block.get("bbox",(0,0,0,0)))
        if block["type"] == 1:
            elements.append(f'<img class="img" src="{escape(block["src"],quote=True)}" style="left:{x0}pt;top:{y0}pt;width:{max(.1,x1-x0)}pt;height:{max(.1,y1-y0)}pt">')
            continue
        for line in block.get("lines",[]):
            for span in line.get("spans",[]):
                value=span.get("text","")
                if not value: continue
                sx,sy,_,_=span.get("bbox",block.get("bbox",(0,0,0,0)))
                color_num=int(span.get("color",0))
                color=f'#{(color_num>>16)&255:02x}{(color_num>>8)&255:02x}{color_num&255:02x}'
                font=escape(str(span.get("font","sans-serif")).replace('"',""))
                flags=int(span.get("flags",0))
                elements.append(f'<span class="txt" style="left:{sx}pt;top:{sy}pt;font-size:{max(1,float(span.get("size",10)))}pt;color:{color};font-family:&quot;{font}&quot;,sans-serif;font-weight:{"700" if flags&16 else "400"};font-style:{"italic" if flags&2 else "normal"}">{escape(value)}</span>')
    bg_tag=f'<img class="bg" src="{escape(bg,quote=True)}">' if bg else ""
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<title>PDF page {n}</title><style>'
        '*{box-sizing:border-box}body{margin:0;background:#eee}'
        f'.page{{position:relative;width:{width}pt;height:{height}pt;background:white;margin:16px auto;overflow:hidden}}'
        '.txt{position:absolute;white-space:pre;line-height:1;z-index:2}'
        '.img{position:absolute;object-fit:fill;z-index:1}'
        '.bg{position:absolute;inset:0;width:100%;height:100%;z-index:0}'
        '</style></head><body><main class="page" data-page="'+str(n)+'">'
        + bg_tag + ''.join(elements) + '</main></body></html>'
    )

def convert_pdf(pdf_path, out_dir, background=False):
    pages_dir, assets_dir = out_dir/"pages", out_dir/"assets"
    pages_dir.mkdir(parents=True,exist_ok=True); assets_dir.mkdir(parents=True,exist_ok=True)
    pages, assets = [], []
    with fitz.open(pdf_path) as doc:
        docmeta=dict(doc.metadata or {})
        docmeta.update(page_count=doc.page_count,is_encrypted=doc.is_encrypted)
        for n,page in enumerate(doc,1):
            blocks=[]; image_idx=0
            for b in page.get_text("dict",sort=False)["blocks"]:
                if b["type"]==0: blocks.append(b)
                elif b["type"]==1:
                    image_idx+=1
                    name=f"page_{n:04d}_image_{image_idx:03d}.{b.get('ext','png')}"
                    (assets_dir/name).write_bytes(b["image"])
                    blocks.append({"type":1,"bbox":b.get("bbox"),"src":f"../assets/{name}"})
                    assets.append(name)
            text=page.get_text("text",sort=True)
            bg=None
            if background:
                name=f"page_{n:04d}_background.png"
                page.get_pixmap(dpi=180,alpha=False).save(assets_dir/name)
                bg=f"../assets/{name}"; assets.append(name)
            width,height=float(page.rect.width),float(page.rect.height)
            html=render_page(n,width,height,blocks,bg)
            (pages_dir/f"page_{n:04d}.html").write_text(html,encoding="utf-8")
            fonts=sorted({s.get("font") for b in blocks for line in b.get("lines",[]) for s in line.get("spans",[]) if s.get("font")})
            image_count=sum(1 for b in blocks if b["type"]==1)
            meta={"text":text,"word_count":len(text.split()),"character_count":len(text),
                  "images_count":image_count,"text_blocks_count":sum(1 for b in blocks if b["type"]==0),
                  "fonts":fonts,"links":[{"uri":x.get("uri"),"from":list(x.get("from",()))} for x in page.get_links() if x.get("uri")],
                  "annotations_count":sum(1 for _ in (page.annots() or [])),
                  "media_box":list(page.mediabox),"crop_box":list(page.cropbox),
                  "coordinate_unit":"PDF points","rendered_background":bool(bg)}
            pages.append({"page_number":n,"width":width,"height":height,"rotation":page.rotation,
                          "text":text,"html":html,"metadata":meta})
    manifest={"source_file":pdf_path.name,"page_count":len(pages),"document_metadata":docmeta,"pages":pages,"assets":assets}
    (out_dir/"document.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    combined='<!doctype html><html><head><meta charset="utf-8"></head><body>'+''.join(
        '<section>'+p["html"][p["html"].find("<main"):p["html"].find("</main>")+7]+'</section>' for p in pages)+'</body></html>'
    (out_dir/"document.html").write_text(combined,encoding="utf-8")
    return manifest

app=FastAPI(title="PDF to HTML API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_methods=["*"],allow_headers=["*"])

@app.on_event("startup")
def startup(): init_db()

@app.get("/health")
def health(): return {"status":"ok"}

@app.post("/api/v1/documents/convert")
async def upload_pdf(file: UploadFile=File(...),include_html: bool=Query(True),render_page_background: bool=Query(False)):
    if not file.filename or not file.filename.lower().endswith(".pdf"): raise HTTPException(400,"Upload a PDF file.")
    DATA.mkdir(parents=True,exist_ok=True); temp=None; size=0
    try:
        with tempfile.NamedTemporaryFile(delete=False,suffix=".pdf",dir=DATA) as f:
            temp=Path(f.name)
            while chunk:=await file.read(1024*1024):
                size+=len(chunk)
                if size>MAX_UPLOAD: raise HTTPException(413,"PDF exceeds 100 MB upload limit.")
                f.write(chunk)
        if not size or temp.read_bytes()[:5]!=b"%PDF-": raise HTTPException(400,"Invalid or empty PDF.")
        doc_id=uuid.uuid4().hex; folder=DATA/"documents"/doc_id
        folder.mkdir(parents=True,exist_ok=True)
        stored=folder/safe_name(file.filename); shutil.move(str(temp),stored); temp=None
        manifest=convert_pdf(stored,folder/"output",render_page_background)
        created=datetime.now(timezone.utc).isoformat()
        with connect() as c:
            c.execute("INSERT INTO documents VALUES(?,?,?,?,?)",(doc_id,file.filename,manifest["page_count"],str(folder),created)); c.commit()
        for p in manifest["pages"]:
            p["html"]=p["html"].replace("../assets/",f"/api/v1/documents/{doc_id}/assets/")
        return {"document_id":doc_id,"source_file":file.filename,"status":"completed",
            "page_count":manifest["page_count"],"document_metadata":manifest["document_metadata"],
            "pages":manifest["pages"] if include_html else None,
            "page_summaries":[{"page_number":p["page_number"],"metadata":p["metadata"]} for p in manifest["pages"]] if not include_html else None,
            "assets":manifest["assets"],"created_at":created}
    except HTTPException: raise
    except Exception as e: raise HTTPException(422,f"Conversion failed: {e}") from e
    finally:
        if temp and temp.exists(): temp.unlink(missing_ok=True)

def get_record(doc_id):
    with connect() as c: row=c.execute("SELECT * FROM documents WHERE id=?",(doc_id,)).fetchone()
    if not row: raise HTTPException(404,"Document not found.")
    return row

def get_manifest(row):
    path=Path(row["folder"])/"output"/"document.json"
    data=json.loads(path.read_text(encoding="utf-8"))
    for p in data["pages"]:
        p["html"]=p["html"].replace("../assets/",f'/api/v1/documents/{row["id"]}/assets/')
    return data

@app.get("/api/v1/documents/{doc_id}")
def document_summary(doc_id: str):
    row=get_record(doc_id); m=get_manifest(row)
    return {"document_id":doc_id,"source_file":row["filename"],"status":"completed","page_count":row["page_count"],"document_metadata":m["document_metadata"],"created_at":row["created_at"]}

@app.get("/api/v1/documents/{doc_id}/json")
def full_json(doc_id: str): return get_manifest(get_record(doc_id))

@app.get("/api/v1/documents/{doc_id}/pages/{page_number}")
def get_page(doc_id: str,page_number: int):
    m=get_manifest(get_record(doc_id))
    if page_number<1 or page_number>len(m["pages"]): raise HTTPException(404,f"Page must be between 1 and {len(m['pages'])}.")
    return {"document_id":doc_id,**m["pages"][page_number-1]}

@app.get("/api/v1/documents/{doc_id}/pages/{page_number}/html",response_class=HTMLResponse)
def get_page_html(doc_id: str,page_number: int): return get_page(doc_id,page_number)["html"]

@app.get("/api/v1/documents/{doc_id}/assets/{filename}")
def get_asset(doc_id: str,filename: str):
    if Path(filename).name!=filename: raise HTTPException(400,"Invalid asset filename.")
    row=get_record(doc_id); path=Path(row["folder"])/"output"/"assets"/filename
    if not path.is_file(): raise HTTPException(404,"Asset not found.")
    return FileResponse(path)

@app.delete("/api/v1/documents/{doc_id}")
def delete_doc(doc_id: str):
    row=get_record(doc_id); shutil.rmtree(row["folder"],ignore_errors=True)
    with connect() as c:
        c.execute("DELETE FROM documents WHERE id=?",(doc_id,)); c.commit()
    return {"document_id":doc_id,"deleted":True}
