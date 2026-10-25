import { useState } from 'react';
import S2BriefWorkspace from './S2BriefWorkspace';

type Props = { version:any; snapshot:any; onSelect:(tab:string)=>void };
const stages = [['Brief','Define intent and source material.'],['Requirements','Review extracted facts before commitment.'],['Program','Turn confirmed requirements into spaces and relationships.'],['Envelope','Apply explicit planning inputs to site geometry.'],['Concepts','Compare deterministic massing alternatives.']] as const;
const API = import.meta.env.VITE_API_BASE_URL || '/api/v1';
export default function S2Workflow({version,snapshot,onSelect}:Props){
 const [expanded,setExpanded]=useState(false); const [stage,setStage]=useState('');
 const status=version?.status||'UNKNOWN'; const token=sessionStorage.getItem('token')||''; const refresh=async()=>{window.dispatchEvent(new Event('ai:s2-refresh'))};
 if(stage==='Brief') return <div><button className="text-btn" onClick={()=>setStage('')}>← S2 overview</button><S2BriefWorkspace api={API} token={token} projectId={snapshot.project.id} version={version} brief={snapshot.brief} onRefresh={refresh}/></div>;
 return <section className="phase-card s2-workflow" aria-labelledby="s2-workflow-title">
  <div className="workflow-head"><div><p className="eyebrow">S2 / DESIGN PIPELINE</p><h2 id="s2-workflow-title">Brief to concept</h2><p className="muted">Each stage consumes canonical project state. Nothing here silently commits design decisions.</p></div><span className={`requirement-state ${String(status).toLowerCase()}`}>{status}</span></div>
  <div className="s2-stage-list">{stages.map(([name,description],index)=><button key={name} className="s2-stage" onClick={()=>name==='Brief'?setStage('Brief'):onSelect(name)} aria-label={`Open ${name} stage`}><span className="stage-index">{index+1}</span><span><strong>{name}</strong><small>{description}</small></span><span aria-hidden="true">→</span></button>)}</div>
  <button className="text-btn" onClick={()=>setExpanded(!expanded)} aria-expanded={expanded}>{expanded?'Hide':'Show'} current dependencies</button>
  {expanded&&<dl className="s2-dependencies"><div><dt>Project version</dt><dd>{version?.label||version?.id||'—'}</dd></div><div><dt>Revision</dt><dd>{version?.revision_number??'—'}</dd></div><div><dt>World Model hash</dt><dd><code>{snapshot?.world_model_revision?.model_hash||'Not available'}</code></dd></div><div><dt>Requirements</dt><dd>{snapshot?.requirements?.length??0} records</dd></div></dl>}
 </section>;
}
