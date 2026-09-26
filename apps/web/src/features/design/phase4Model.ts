export const REVIEW_ACTIONS=['ACCEPT_FOR_FEASIBILITY','REQUEST_CHANGES','BLOCK'] as const;
export function workflowProgress(steps:{state:string}[]){const done=steps.filter(x=>x.state==='SUCCEEDED').length;return {done,total:steps.length,percent:steps.length?Math.round(done/steps.length*100):0}}
export function groundingTone(status:string){return status==='GROUNDED'?'trusted':status==='UNGROUNDED'?'warning':'review'}
export function usageTotal(rows:{calls:number;tokens:number;estimated_cost_usd:number}[]){return rows.reduce((a,x)=>({calls:a.calls+x.calls,tokens:a.tokens+x.tokens,cost:a.cost+x.estimated_cost_usd}),{calls:0,tokens:0,cost:0})}
