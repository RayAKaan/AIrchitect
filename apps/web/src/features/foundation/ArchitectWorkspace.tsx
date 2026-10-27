import ProductWorkspace from './ProductWorkspace';

export default function ArchitectWorkspace({ api, token, project, onClose }: { api: string; token: string; project: any; onClose: () => void }) {
  return <ProductWorkspace api={api} token={token} project={project} onClose={onClose} />;
}
