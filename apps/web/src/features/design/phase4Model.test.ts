import {describe,expect,it} from 'vitest';
import {groundingTone,REVIEW_ACTIONS,usageTotal,workflowProgress} from './phase4Model';
describe('Phase 4 trust UI model',()=>{
 it('exposes only the mandatory review dispositions',()=>expect(REVIEW_ACTIONS).toEqual(['ACCEPT_FOR_FEASIBILITY','REQUEST_CHANGES','BLOCK']));
 it('does not count a human waiting gate as completed',()=>expect(workflowProgress([{state:'SUCCEEDED'},{state:'WAITING_HUMAN_REVIEW'}])).toEqual({done:1,total:2,percent:50}));
 it('makes ungrounded output a warning',()=>expect(groundingTone('UNGROUNDED')).toBe('warning'));
 it('aggregates provider usage',()=>expect(usageTotal([{calls:2,tokens:10,estimated_cost_usd:.01},{calls:1,tokens:5,estimated_cost_usd:.02}])).toEqual({calls:3,tokens:15,cost:.03}));
});
