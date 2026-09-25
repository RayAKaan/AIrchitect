from app.domains.validation.schemas import ValidationRequest
from app.domains.validation.engine import evaluate

def req(**kw):
 d=dict(project_id='p',artifact_id='a',artifact_version='v1',source_hash='h1',current_source_hash='h1',checks=[dict(check_id='c',category='geometry',status='passed',message='ok')],evidence=[],declared_current=True);d.update(kw);return ValidationRequest(**d)

def test_ready_for_review_is_not_approval():
 r=evaluate(req()); assert r.status=='ready_for_review'; assert any('not regulatory approval' in x for x in r.limitations)
def test_stale_hash_overrides_passes():
 r=evaluate(req(current_source_hash='h2')); assert r.status=='stale' and not r.current
def test_required_unknown_blocks():
 r=evaluate(req(checks=[dict(check_id='c',category='code',status='unknown',message='missing')])); assert r.status=='blocked'
def test_unverified_evidence_blocks():
 r=evaluate(req(checks=[dict(check_id='c',category='x',status='passed',message='ok',evidence_ids=['e'])],evidence=[dict(evidence_id='e',source_type='document',source_ref='doc://x',version='1',description='source',verified=False)])); assert r.status=='blocked' and r.missing_evidence==['c:e']
def test_human_review_marks_incomplete():
 r=evaluate(req(checks=[dict(check_id='c',category='x',status='passed',message='ok',requires_human_review=True)])); assert r.status=='incomplete' and r.human_review_required
