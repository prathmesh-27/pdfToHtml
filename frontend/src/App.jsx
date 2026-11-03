
import React,{useState}from'react';
const API='/api/v1';
export default function App(){
 const[file,setFile]=useState(null),[doc,setDoc]=useState(null),[page,setPage]=useState(null),[n,setN]=useState(1),[busy,setBusy]=useState(false),[error,setError]=useState(''),[bg,setBg]=useState(false),[json,setJson]=useState(false);
 async function load(id,num){try{const r=await fetch(`${API}/documents/${id}/pages/${num}`),d=await r.json();if(!r.ok)throw Error(d.detail);setPage(d);setN(num);setError('')}catch(e){setError(e.message)}}
 async function convert(){if(!file)return;setBusy(true);setError('');try{const f=new FormData();f.append('file',file);const r=await fetch(`${API}/documents/convert?include_html=false&render_page_background=${bg}`,{method:'POST',body:f});const d=await r.json();if(!r.ok)throw Error(d.detail);setDoc(d);await load(d.document_id,1)}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function remove(){await fetch(`${API}/documents/${doc.document_id}`,{method:'DELETE'});setDoc(null);setPage(null);setFile(null)}
 return <div className="app"><header><b>▣ PDF to HTML Studio</b><span>● API workspace</span></header><main>
 <section className="hero"><label>PDF CONVERSION ENGINE</label><h1>Turn complex PDFs into<br/><em>structured HTML.</em></h1><p>Upload a PDF, extract page-level HTML and metadata, then inspect any page through the API.</p></section>
 <section className="card"><h2>Upload document</h2><p>PDF files only · Local conversion</p><label className="drop"><input type="file" accept=".pdf,application/pdf" onChange={e=>setFile(e.target.files[0])}/><b>⇧ {file?file.name:'Choose a PDF from your device'}</b><small>Click to browse files</small></label><div className="actions"><label><input type="checkbox" checked={bg} onChange={e=>setBg(e.target.checked)}/> Visual page-image fallback</label><button disabled={!file||busy} onClick={convert}>{busy?'Converting…':'Convert PDF'}</button></div>{error&&<p className="error">{error}</p>}</section>
 {doc&&<section className="card"><div className="row"><div><h2>{doc.source_file}</h2><small>{doc.page_count} pages · ID {doc.document_id}</small></div><button className="delete" onClick={remove}>Delete</button></div><div className="stats"><span><small>PAGES</small><b>{doc.page_count}</b></span><span><small>STATUS</small><b>Completed</b></span><span><small>PAGE SIZE</small><b>{page?`${Math.round(page.width)} × ${Math.round(page.height)} pt`:'—'}</b></span><span><small>IMAGES</small><b>{page?.metadata.images_count??0}</b></span></div>
 <div className="row"><div><h2>Page inspector</h2><small>HTML and metadata returned by page number</small></div><div><button disabled={n<=1} onClick={()=>load(doc.document_id,n-1)}>‹</button> Page {n}/{doc.page_count} <button disabled={n>=doc.page_count} onClick={()=>load(doc.document_id,n+1)}>›</button></div></div>
 <nav><button className={!json?'selected':''} onClick={()=>setJson(false)}>HTML preview</button><button className={json?'selected':''} onClick={()=>setJson(true)}>Page JSON</button><a href={`${API}/documents/${doc.document_id}/pages/${n}/html`} target="_blank">Open HTML ↗</a></nav>
 {json?<pre>{JSON.stringify(page,null,2)}</pre>:<iframe title="Page HTML" srcDoc={page?.html||''} sandbox="allow-same-origin"/>}
 <div className="api"><b>GET /api/v1/documents/{doc.document_id}/pages/{n}</b><small>Returns HTML string, extracted text and page metadata as JSON.</small></div></section>}
 <footer>FastAPI + React · Local storage</footer></main></div>
}
