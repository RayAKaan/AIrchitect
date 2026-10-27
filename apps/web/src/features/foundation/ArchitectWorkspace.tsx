import FoundationWorkspace from './FoundationWorkspace';

export default function ArchitectWorkspace({api, token, project, onClose}:{api:string;token:string;project:any;onClose:()=>void}) {
  return <FoundationWorkspace api={api} token={token} project={project} onClose={onClose}/>;
}
