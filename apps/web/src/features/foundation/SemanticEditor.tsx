import {useCallback,useEffect,useMemo,useState} from 'react';

type ElementRow={id:string;element_type:string;name:string;identity_key:string;properties:Record<string,{value:any;unit?:string|null;data_type?:string}>;designer_authored?:boolean;cad_mapping?:{ifc_class:string;cad_feature:string;required_parameters:string[]}};
type Props={api:string;token:string;projectId:string;version:any;onChanged:()=>Promise<void>};

const EDITABLE:Record<string,string[]> = {
  Site:['area_m2','width_m','depth_m','orientation_deg','city'],
  Building:['use','floor_count','floor_to_floor_height_m','height_m','target_gfa_m2','coverage_ratio','footprint_width_m','footprint_depth_m'],
  Storey:['elevation_m','floor_to_floor_height_m','area_m2'],
  Space:['use','area_m2','level_number'],
  ParkingFacility:['arrangement','spaces'],
  Wall:['length_m','height_m','thickness_m','level_number'],
  Slab:['width_m','depth_m','thickness_m','level_number'],
  Roof:['footprint_width_m','footprint_depth_m','level_number'],
  Door:['width_m','height_m','level_number'],
  Window:['width_m','height_m','level_number'],
};
const numeric=(key:string)=>key!=='city'&&key!=='use'&&key!=='arrangement';
const defaults:Record<string,string>={
  Space:'{"use":"office","area_m2":25}',
  Wall:'{"length_m":5,"height_m":3,"thickness_m":0.2}',
  Slab:'{"width_m":5,"depth_m":4,"thickness_m":0.2}',
  Roof:'{"footprint_width_m":20,"footprint_depth_m":15}',
  Door:'{"width_m":0.9,"height_m":2.1}',
  Window:'{"width_m":1.2,"height_m":1.5}',
};

export default function SemanticEditor({api,token,projectId,version,onChanged}:Props){
  const [semantic,setSemantic]=useState<any>(null);
  const [state,setState]=useState<any>(null);
  const [selectedId,setSelectedId]=useState('');
  const [property,setProperty]=useState('');
  const [value,setValue]=useState('');
  const [reason,setReason]=useState('Designer refinement');
  const [loading,setLoading]=useState(false);
  const [saving,setSaving]=useState(false);
  const [error,setError]=useState('');
  const [plan,setPlan]=useState<any>(null);
  const [regeneration,setRegeneration]=useState<any>(null);
  const [newType,setNewType]=useState('Wall');
  const [newName,setNewName]=useState('Wall 1');
  const [newLevel,setNewLevel]=useState('1');
  const [newHost,setNewHost]=useState('');
  const [hostSelection,setHostSelection]=useState('');
  const [newProperties,setNewProperties]=useState(defaults.Wall);
  const call=useCallback(async(path:string,init:RequestInit={})=>{
    const headers={Authorization:`Bearer ${token}`,'Content-Type':'application/json'};
    const response=await fetch(api+path,{...init,headers:{...headers,...init.headers}});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.error?.message||data.detail?.error?.message||data.detail||`Request failed (${response.status})`);
    return data;
  },[api,token]);
  const base=`/projects/${projectId}/versions/${version.id}/semantic-model`;
  const elements:ElementRow[]=semantic?.semantic_model?.elements||[];
  const selected=elements.find(element=>element.id===selectedId)||elements.find(element=>element.element_type==='Building')||elements[0];
  const directLocked=Boolean(state?.locks?.[selected?.id]?.locked);
  const lockedAncestorId=useMemo(()=>{
    if(!selected||!semantic||!state)return null;
    const lockedIds=new Set(Object.entries(state.locks||{}).filter(([,info]:any)=>info?.locked).map(([id])=>id));
    const parents:Record<string,string[]>={};
    for(const relationship of semantic.semantic_model.relationships||[]){
      const source=relationship.source_id,target=relationship.target_id;
      const parent=relationship.relationship_type==='located_on'?target:source;
      const child=relationship.relationship_type==='located_on'?source:target;
      (parents[child] ||= []).push(parent);
    }
    const seen=new Set<string>();const queue=[selected.id];
    while(queue.length){
      const current=queue.shift()!;
      if(seen.has(current))continue;
      seen.add(current);
      if(lockedIds.has(current))return current;
      queue.push(...(parents[current]||[]).filter((id:string)=>!seen.has(id)));
    }
    return null;
  },[selected,semantic,state]);
  const locked=directLocked||Boolean(lockedAncestorId);
  const currentHostId=semantic?.semantic_model?.relationships?.find((relationship:any)=>relationship.target_id===selected?.id&&relationship.relationship_type==='hosts_opening')?.source_id||'';
  const editable=version.status==='DRAFT';
  const revision=state?.revision_number??version.revision_number;

  const load=useCallback(async()=>{
    setLoading(true);
    try{
      const [semanticResponse,stateResponse]=await Promise.all([
        call(`/projects/${projectId}/versions/${version.id}/semantic-model`),
        call(`/projects/${projectId}/versions/${version.id}/semantic-model/designer-state`)
      ]);
      setSemantic(semanticResponse);setState(stateResponse);
      setSelectedId(current=>semanticResponse.semantic_model.elements.some((item:ElementRow)=>item.id===current)?current:
        semanticResponse.semantic_model.elements.find((item:ElementRow)=>item.element_type==='Building')?.id||semanticResponse.semantic_model.elements[0]?.id||'');
      setError('');
    }catch(e){setError(e instanceof Error?e.message:'Could not load semantic model');}
    finally{setLoading(false);}
  },[call,projectId,version.id]);
  useEffect(()=>{void load()},[load]);

  useEffect(()=>{
    if(!selected)return;
    const choices=EDITABLE[selected.element_type]||[];
    const nextProperty=choices.includes(property)?property:(choices[0]||'');
    setProperty(nextProperty);
    const item=selected.properties?.[nextProperty];
    setValue(item?.value===undefined||item?.value===null?'':String(item.value));
  },[selected,property]);
  useEffect(()=>{setHostSelection(currentHostId)},[selectedId,semantic,currentHostId]);

  const currentValue=useMemo(()=>selected?.properties?.[property]?.value,[selected,property]);
  async function mutate(path:string,body:any,method='POST'){
    setSaving(true);setError('');
    try{
      const result=await call(path,{method,body:JSON.stringify(body)});
      if(result.version?.revision_number&&state)setState({...state,revision_number:result.version.revision_number});
      await load();await onChanged();
      return result;
    }catch(e){setError(e instanceof Error?e.message:'Designer operation failed');return null}
    finally{setSaving(false)}
  }
  async function edit(){
    if(!selected||!property)return;
    const parsed=numeric(property)?Number(value):value;
    if(numeric(property)&&value.trim()===''){setError('Enter a numeric value.');return}
    if(numeric(property)&&!Number.isFinite(parsed)){setError('Enter a finite numeric value.');return}
    await mutate(`${base}/elements/${selected.id}`,{property,value:parsed,reason,expected_revision:revision},'PATCH');
  }
  async function toggleLock(){
    if(!selected)return;
    await mutate(`${base}/elements/${selected.id}/${locked?'unlock':'lock'}`,{
      reason:reason|| (locked?'Designer unlock':'Protect this element'),expected_revision:revision
    });
  }
  async function saveHost(){
    if(!selected)return;
    await mutate(`${base}/elements/${selected.id}/host`,{
      host_element_id:hostSelection||null,reason,expected_revision:revision
    },'PATCH');
  }
  async function addElement(){
    try{
      const props=JSON.parse(newProperties);
      if(!props||Array.isArray(props)||typeof props!=='object')throw new Error('Properties must be a JSON object.');
      const body={element_type:newType,name:newName,properties:props,level_number:newLevel?Number(newLevel):null,host_element_id:['Door','Window'].includes(newType)&&newHost?newHost:null,reason,expected_revision:revision};
      const result=await mutate(`${base}/elements`,body);
      if(result?.event?.element_id)setSelectedId(result.event.element_id);
    }catch(e){setError(e instanceof Error?e.message:'Invalid properties JSON')}
  }
  async function removeElement(){
    if(!selected?.designer_authored)return;
    if(!window.confirm(`Delete ${selected.name}? This can be undone while this version remains a draft.`))return;
    await mutate(`${base}/elements/${selected.id}`,{reason,expected_revision:revision},'DELETE');
  }
  async function loadPlan(){
    if(!selected)return;
    try{setPlan(await call(`${base}/regeneration-plan?element_id=${selected.id}`));setError('')}
    catch(e){setError(e instanceof Error?e.message:'Could not build regeneration plan')}
  }
  async function regenerate(){
    if(!semantic)return;
    try{
      setSaving(true);setError('');
      const targets=plan?.target_element_id===selected?.id&&plan?.world_model_hash===semantic.world_model_hash
        ?plan.regeneration_candidate_ids:[selected?.id].filter(Boolean);
      const result=await call(`${base}/regenerate`,{method:'POST',body:JSON.stringify({
        element_ids:targets,expected_world_model_hash:semantic.world_model_hash
      })});
      setRegeneration(result.specification);
    }catch(e){setError(e instanceof Error?e.message:'Selective regeneration failed')}
    finally{setSaving(false)}
  }
  return <section className="semantic-editor">
    <header className="semantic-editor-head">
      <div><p className="eyebrow">PHASE 25 / DESIGNER CONTROL</p><h2>Semantic model editor</h2>
        <p className="muted">Edits are versioned, validated and reversible. Locked elements are protected from edits and regeneration.</p></div>
      <div className="semantic-toolbar">
        <button className="btn outline small" disabled={!editable||saving||!state?.can_undo} onClick={()=>void mutate(`${base}/undo`,{expected_revision:revision})}>Undo</button>
        <button className="btn outline small" disabled={!editable||saving||!state?.can_redo} onClick={()=>void mutate(`${base}/redo`,{expected_revision:revision})}>Redo</button>
        <button className="btn outline small" disabled={saving} onClick={()=>void load()}>Refresh</button>
      </div>
    </header>
    {!editable&&<div className="editor-notice">This version is {version.status}. Create a new draft version to edit it; historical versions remain immutable.</div>}
    {error&&<div className="alert" role="alert">{error}</div>}
    {(semantic?.consistency_issues||[]).length>0&&<div className="editor-notice" role="status">
      <b>Model review findings</b>
      {(semantic.consistency_issues as any[]).map((issue:any,index:number)=><p key={issue.code+'-'+index}><b>{issue.code.replaceAll('_',' ')}</b>: {issue.message||issue.reason||'Review this model consistency finding before proceeding.'}</p>)}
      <small>These automated findings are preliminary and do not constitute code, structural or engineering approval.</small>
    </div>}
    {loading?<p className="muted" role="status">Loading editable semantic graph…</p>:<div className="semantic-editor-grid">
      <aside className="phase-card semantic-element-list"><h3>Elements ({elements.length})</h3>
        {elements.map(element=><button key={element.id} className={selected?.id===element.id?'semantic-element active':'semantic-element'} onClick={()=>setSelectedId(element.id)}>
          <span><b>{element.name}</b><small>{element.element_type}{element.designer_authored?' · authored':''}</small></span>
          {state?.locks?.[element.id]?.locked&&<span className="state locked">Locked</span>}
        </button>)}
      </aside>
      <div className="semantic-editor-main">
        {selected?<article className="phase-card">
          <div className="semantic-element-title"><div><p className="eyebrow">{selected.element_type}</p><h3>{selected.name}</h3><small>{selected.id}</small></div>
            <button className={directLocked?'btn primary small':'btn outline small'} disabled={!editable||saving||(!directLocked&&Boolean(lockedAncestorId))} onClick={()=>void toggleLock()}>{directLocked?'Unlock element':lockedAncestorId?'Protected by ancestor':'Lock element'}</button></div>
          <p className="muted">IFC mapping: {selected.cad_mapping?.ifc_class} · feature intent: {selected.cad_mapping?.cad_feature}</p>
          <div className="semantic-property-grid">{Object.entries(selected.properties||{}).map(([key,item])=><div className="semantic-property" key={key}><small>{key.replaceAll('_',' ')}</small><b>{String((item as any)?.value)} {(item as any)?.unit||''}</b></div>)}</div>
          <div className="semantic-edit-form">
            <label>Property<select value={property} onChange={event=>{setProperty(event.target.value);setValue(selected.properties?.[event.target.value]?.value===undefined?'':String(selected.properties[event.target.value].value))}}>{(EDITABLE[selected.element_type]||[]).map(key=><option key={key} value={key}>{key.replaceAll('_',' ')}</option>)}</select></label>
            <label>New value<input value={value} onChange={event=>setValue(event.target.value)} placeholder={currentValue===undefined?'Not set':String(currentValue)} disabled={!editable||saving||locked}/></label>
            <label className="wide">Reason / change note<input value={reason} onChange={event=>setReason(event.target.value)} maxLength={1000}/></label>
            <button className="btn primary" disabled={!editable||saving||locked||!property||value.trim()===''} onClick={()=>void edit()}>Apply edit</button>
            {selected.designer_authored&&<button className="btn outline" disabled={!editable||saving||locked} onClick={()=>void removeElement()}>Delete element</button>}
          </div>
          {selected.designer_authored&&['Door','Window'].includes(selected.element_type)&&<div className="semantic-edit-form">
            <label className="wide">Wall host<select value={hostSelection} onChange={event=>setHostSelection(event.target.value)} disabled={!editable||saving||locked}>
              <option value="">No host (underconstrained)</option>{elements.filter(element=>element.element_type==='Wall').map(wall=><option key={wall.id} value={wall.id}>{wall.name}</option>)}
            </select></label>
            <button className="btn outline" disabled={!editable||saving||locked||hostSelection===currentHostId} onClick={()=>void saveHost()}>Update wall host</button>
          </div>}
          {locked&&<p className="editor-notice">{directLocked?'Protected: unlock this element before changing or deleting it.':`Protected by locked ancestor: ${elements.find(element=>element.id===lockedAncestorId)?.name||lockedAncestorId}. Unlock the ancestor to edit this element.`}</p>}
        </article>:<div className="phase-card">No semantic elements are available.</div>}
        {editable&&<article className="phase-card">
          <p className="eyebrow">AUTHOR A COMPONENT</p><h3>Add a semantic element</h3>
          <div className="semantic-edit-form">
            <label>Type<select value={newType} onChange={event=>{setNewType(event.target.value);setNewProperties(defaults[event.target.value]||'{}');setNewName(`${event.target.value} 1`);setNewHost('')}}>{['Space','Wall','Slab','Roof','Door','Window'].map(type=><option key={type}>{type}</option>)}</select></label>
            <label>Name<input value={newName} onChange={event=>setNewName(event.target.value)} maxLength={120}/></label>
            <label>Storey (optional)<input type="number" min="1" value={newLevel} onChange={event=>setNewLevel(event.target.value)}/></label>
            {['Door','Window'].includes(newType)&&<label>Host wall<select value={newHost} onChange={event=>setNewHost(event.target.value)}><option value="">No host (underconstrained)</option>{elements.filter(element=>element.element_type==='Wall').map(wall=><option key={wall.id} value={wall.id}>{wall.name}</option>)}</select></label>}
            <label className="wide">Typed properties (JSON)<textarea value={newProperties} onChange={event=>setNewProperties(event.target.value)} rows={3}/></label>
            <button className="btn primary" disabled={saving||!newName.trim()} onClick={()=>void addElement()}>Add element</button>
          </div>
        </article>}
        <article className="phase-card">
          <p className="eyebrow">SELECTIVE REGENERATION</p><h3>Impact and feature-intent refresh</h3>
          <div className="semantic-toolbar"><button className="btn outline small" disabled={saving||!selected} onClick={()=>void loadPlan()}>Preview impact</button>
            <button className="btn primary small" disabled={saving||!semantic||!selected} onClick={()=>void regenerate()}>Regenerate selected intents</button></div>
          {plan&&<div className="regeneration-result"><b>Impact plan · {plan.recompute_groups.length} downstream groups</b><p>{plan.affected_element_ids.length} affected · {plan.eligible_element_ids.length} eligible for intent refresh · {plan.protected_element_ids.length} protected</p><div>{plan.recompute_groups.map((group:string)=><span className="state" key={group}>{group.replaceAll('_',' ')}</span>)}</div></div>}
          {regeneration&&<div className="regeneration-result"><b>Result: {regeneration.status}</b><p>{regeneration.intents.length} feature intents refreshed. Protected elements skipped: {regeneration.protected_element_ids.length}.</p>{regeneration.intents.map((intent:any)=><div className="prov-row" key={intent.element_id}><b>{intent.element_type} · {intent.feature}</b><span>{intent.status}{intent.missing_parameters?.length?' · missing: '+intent.missing_parameters.join(', '):''}</span>{intent.placement&&<small>Placement: Level {intent.placement.level_number??'unknown'} · elevation {intent.placement.elevation_m??'unknown'} m</small>}{intent.warnings?.map((warning:string)=><small className="editor-notice" key={warning}>{warning}</small>)}</div>)}<small>Intent regeneration does not create a native CAD solid or exchange file.</small></div>}
        </article>
        <article className="phase-card"><p className="eyebrow">EDIT HISTORY</p><h3>Recent actions</h3>
          {state?.history?.length?state.history.slice(-12).reverse().map((event:any)=><div className="history-row" key={event.event_id}><div><b>{event.action.replaceAll('_',' ')}</b><small>{event.property||event.element_type||event.target_event_id||event.reason||'Semantic model action'}</small></div><time>{new Date(event.created_at).toLocaleString()}</time></div>):<p className="muted">No designer actions have been recorded.</p>}
        </article>
      </div>
    </div>}
  </section>;
}
