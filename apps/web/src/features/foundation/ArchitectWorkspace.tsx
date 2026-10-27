import UnifiedWorkspace from './UnifiedWorkspace';

export default function ArchitectWorkspace({ api, token, project, onClose }: { api: string; token: string; project: any; onClose: () => void }) {
  return <UnifiedWorkspace api={api} token={token} project={project} onClose={onClose} />;
}
