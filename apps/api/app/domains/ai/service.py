import re
from app.domains.requirements.extractor import DeterministicRequirementExtractor

INJECTION=re.compile(r'(?i)(ignore\s+(all\s+)?(previous|system)|reveal\s+(the\s+)?(prompt|secret|api key)|execute\s+(sql|shell)|bypass\s+(authorization|review))')
REQUIRED={'site_area':'site dimensions or boundary','target_gfa':'target gross floor area','floor_count':'floor count or height','budget':'budget or cost constraint','parking_spaces':'parking requirement'}

def deterministic_extraction(text:str)->dict:
 candidates=DeterministicRequirementExtractor().extract(text); present={x.parameter for x in candidates}
 facts=[{'parameter':x.parameter,'value':x.normalized_value,'unit':x.unit,'confidence':x.confidence,'source_text':x.source_text} for x in candidates]
 clarifications=[]
 for key,label in REQUIRED.items():
  if key not in present:clarifications.append({'id':'clarify-'+key,'parameter':key,'question':f'Please confirm the {label}.','reason':'Required deterministic feasibility input is unresolved.','priority':'HIGH' if key in {'site_area','floor_count'} else 'MEDIUM'})
 return {'schema_version':'1.0.0','facts':facts,'ambiguities':[],'clarifications':clarifications,'assumptions':[],'injection_detected':bool(INJECTION.search(text))}
