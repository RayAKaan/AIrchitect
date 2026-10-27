import S2ConceptGenerationWorkspace from './S2ConceptGenerationWorkspace';
import S2ConceptExplorer from './S2ConceptExplorer';
import './ExploreWorkspace.css';

type Props = { api: string; token: string; projectId: string; version: any; onOpenWorldModel: () => void };

export default function ExploreWorkspace({ api, token, projectId, version, onOpenWorldModel }: Props) {
  const committed = version.status === 'COMMITTED';
  return <section className="explore-workspace"><header className="explore-header"><div><p className="eyebrow">EXPLORE / CONCEPTS</p><h2>Compare possible directions</h2><p>AIrchitect generates bounded alternatives from a committed canonical world model, then lets you inspect and select the direction you want to develop.</p></div><span className={`requirement-state ${committed ? 'confirmed' : 'proposed'}`}>{committed ? 'READY' : 'COMMIT REQUIRED'}</span></header>{!committed && <div className="explore-prerequisite"><div><b>The world model is still editable.</b><p>Concept generation is intentionally blocked until the current world model is committed. This keeps generated alternatives tied to an immutable canonical input.</p></div><button className="btn primary" onClick={onOpenWorldModel}>Review world model</button></div>}<div className="unified-stack"><S2ConceptGenerationWorkspace api={api} token={token} projectId={projectId} version={version}/><S2ConceptExplorer api={api} token={token} projectId={projectId} version={version}/></div></section>;
}
