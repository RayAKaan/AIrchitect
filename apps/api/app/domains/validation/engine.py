from .schemas import ValidationRequest, ValidationResponse

def evaluate(body: ValidationRequest) -> ValidationResponse:
    evidence={e.evidence_id:e for e in body.evidence}
    missing=[]
    for check in body.checks:
        for eid in check.evidence_ids:
            if eid not in evidence or not evidence[eid].verified:
                missing.append(f'{check.check_id}:{eid}')
    current=body.declared_current and body.source_hash == body.current_source_hash
    failed=sum(c.status=='failed' for c in body.checks)
    unknown=sum(c.status=='unknown' for c in body.checks)
    passed=sum(c.status=='passed' for c in body.checks)
    required_block=any(c.required and c.status in ('failed','unknown') for c in body.checks)
    if not current: status='stale'
    elif required_block or missing: status='blocked'
    elif unknown or any(c.requires_human_review for c in body.checks): status='incomplete'
    else: status='ready_for_review'
    return ValidationResponse(artifact_id=body.artifact_id, artifact_version=body.artifact_version,
        status=status,current=current,passed=passed,failed=failed,unknown=unknown,
        missing_evidence=sorted(set(missing)),
        human_review_required=any(c.requires_human_review for c in body.checks) or status!='ready_for_review',
        checks=body.checks,evidence=body.evidence,
        limitations=['Readiness is not regulatory approval, engineering certification, or permission to construct.',
        'Evidence verification is asserted by the caller; this endpoint does not independently authenticate source documents.'])
