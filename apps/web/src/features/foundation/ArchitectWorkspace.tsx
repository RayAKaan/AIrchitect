import { useState } from 'react';
import FoundationWorkspace from './FoundationWorkspace';
import WorkspaceFlow from './WorkspaceFlow';
import './WorkspaceFlow.css';

export default function ArchitectWorkspace({api, token, project, onClose}:{api:string;token:string;project:any;onClose:()=>void}) {
  const [stage, setStage] = useState('Brief');
  function selectStage(next:string) {
    setStage(next);
    window.dispatchEvent(new CustomEvent('airchitect:workspace-stage', { detail: { stage: next, projectId: project.id } }));
  }
  return <section className="architect-workspace-shell">
    <WorkspaceFlow active={stage} onSelect={selectStage}/>
    <FoundationWorkspace api={api} token={token} project={project} onClose={onClose}/>
  </section>;
}
