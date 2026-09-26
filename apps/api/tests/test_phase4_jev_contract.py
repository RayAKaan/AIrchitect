import httpx,pytest
from app.core.config import settings
from app.domains.decisions.providers import JevProvider
from app.domains.decisions.schemas import DecisionRequest

class FakeResponse:
 def __init__(self,data):self._data=data;self.headers={'x-request-id':'jev-request-1'}
 def raise_for_status(self):pass
 def json(self):return self._data
class FakeClient:
 sent=None
 def __init__(self,*args,**kwargs):pass
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 async def post(self,url,headers,json):FakeClient.sent=(url,headers,json);return FakeResponse({'model':'jev-1.13.0','answers':{'decision':{'type':'choice','choice':'REVIEW','confidence':.74,'probabilities':{'CONTINUE':.26,'REVIEW':.74}}},'usage':{'input_tokens':20,'output_tokens':4}})

@pytest.mark.asyncio
async def test_official_jev_systemone_choice_contract(monkeypatch):
 monkeypatch.setattr(settings,'jev_enabled',True);monkeypatch.setattr(settings,'jev_api_key','server-secret');monkeypatch.setattr(httpx,'AsyncClient',FakeClient)
 request=DecisionRequest(decision_type='routing',context={'unknowns':['height']},allowed_options=['CONTINUE','REVIEW'],metadata={'jev_primitive':'choice','option_descriptions':{'CONTINUE':'Proceed','REVIEW':'Human review'}})
 result=await JevProvider().decide(request);url,headers,body=FakeClient.sent
 assert url=='https://api.typesafe.ai/v1/systemone' and headers['Authorization']=='Bearer server-secret'
 assert body['model']=='jev-latest' and body['questions']['decision']['type']=='choice'
 assert result.selected_option=='REVIEW' and result.provider_version=='jev-1.13.0' and result.metadata['usage']['input_tokens']==20
 monkeypatch.setattr(settings,'jev_enabled',False);monkeypatch.setattr(settings,'jev_api_key','')

@pytest.mark.asyncio
async def test_jev_noul_requires_explicit_binary_mapping(monkeypatch):
 monkeypatch.setattr(settings,'jev_enabled',True);monkeypatch.setattr(settings,'jev_api_key','server-secret')
 with pytest.raises(ValueError,match='explicit yes_option'):
  await JevProvider().decide(DecisionRequest(decision_type='block',allowed_options=['BLOCK','CONTINUE'],metadata={'jev_primitive':'noul'}))
 monkeypatch.setattr(settings,'jev_enabled',False);monkeypatch.setattr(settings,'jev_api_key','')
