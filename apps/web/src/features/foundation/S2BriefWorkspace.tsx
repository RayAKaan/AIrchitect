import { useEffect, useState } from 'react';

type Props={api:string;token:string;projectId:string;version:any;brief:any;onRefresh:()=>Promise<void>};
export default function S2BriefWorkspace({api,token,projectId,version,brief,onRefresh}:Props){
 const [text,setText]=useState(brief?.raw_text||''); const [source,setSource]=useState(brief?.source_reference||''); const [busy,setBusy]=useState(false); const [error,setError]=useState('');
 useEffect(()=>{setText(brief?.raw_text||'');setSource(brief?.source_reference||'')},[brief?.id,brief?.revision]);
 async function save(){setBusy(true);setError('');try{const r=await fetch(`${api}/projects/${projectId}/versions/${version.id}/brief`,{method:'PUT',headers:{'Content-Type':'application/json',Authorization:`Bearer ${token}`},body:JSON.stringify({text,source_reference:source||null,source_type:'USER_BRIEF'})});if(!r.ok){const d=await r.json().catch(()=>({}));throw Error(d.detail||'Could not save brief')}await onRefresh()}catch(e){setError(e instanceof Error?e.message:'Could not save brief')}finally{setBusy(false)}}
 const dirty=text!==String(brief?.raw_text||'')||source!==String(brief?.source_reference||'');
 return <div className="phase-card"><div className="workflow-head"><div><p className="eyebrow">S2 / BRIEF</p><h2>Project brief</h2><p className="muted">Write the source intent. Extraction remains separate and nothing is confirmed automatically.</p></div><span className={`requirement-state ${dirty?'proposed':'confirmed'}`}>{dirty?'UNSAVED':'CURRENT'}</span></div>
  <label>Architectural brief<textarea value={text} onChange={e=>setText(e.target.value)} disabled={version.status!=='DRAFT'} placeholder="Describe building type, users, area targets, floors, parking, operational needs and other known intent…" aria-label="Architectural brief"/></label>
  <label>Source reference <input value={source} onChange={e=>setSource(e.target.value)} disabled={version.status!=='DRAFT'} placeholder="Optional document, client reference, or meeting note"/></label>
  {error&&<div className="alert" role="alert">{error}</div>}
  <div className="card-actions"><button className="btn primary" disabled={busy||version.status!=='DRAFT'||!text.trim()} onClick={save}>{busy?'Saving…':'Save canonical brief'}</button><span>{brief?`Revision ${brief.revision} · ${brief.content_hash?.slice(0,16)}…`:'No brief saved for this version.'}</span></div>
  <small>Saving creates a version-scoped canonical record. Regulatory values are not inferred from this text.</small>
 </div>;
}
