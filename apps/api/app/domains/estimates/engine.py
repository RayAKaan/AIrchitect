import hashlib, json
from .schemas import EstimateRequest, EstimateResponse, EstimateLine

def calculate(req: EstimateRequest) -> EstimateResponse:
    quantities = {q.code: q for q in req.quantities}
    lines = []
    for item in sorted(req.lines, key=lambda x: (x.category, x.quantity_code)):
        q = quantities[item.quantity_code]
        r = item.rate
        lines.append(EstimateLine(category=item.category, quantity_code=q.code, quantity=q.quantity, unit=q.unit,
            rate_low_sar=r.low, rate_base_sar=r.base, rate_high_sar=r.high,
            total_low_sar=round(q.quantity*r.low, 2), total_base_sar=round(q.quantity*r.base, 2),
            total_high_sar=round(q.quantity*r.high, 2), rate_source=r.source, rate_schedule_version=r.rate_schedule_version))
    low = round(sum(x.total_low_sar for x in lines), 2)
    base = round(sum(x.total_base_sar for x in lines), 2)
    high = round(sum(x.total_high_sar for x in lines), 2)
    factor = req.contingency_pct / 100
    canonical = req.model_dump(mode='json')
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return EstimateResponse(estimate_id=f'est-{digest[:20]}', project_id=req.project_id,
        source_revision=req.source_revision, geometry_artifact_id=req.geometry_artifact_id,
        geometry_sha256=req.geometry_sha256, subtotal_low_sar=low, subtotal_base_sar=base, subtotal_high_sar=high,
        contingency_pct=req.contingency_pct, contingency_low_sar=round(low*factor,2),
        contingency_base_sar=round(base*factor,2), contingency_high_sar=round(high*factor,2),
        total_low_sar=round(low*(1+factor),2), total_base_sar=round(base*(1+factor),2),
        total_high_sar=round(high*(1+factor),2), lines=lines,
        caveats=['Preliminary feasibility estimate only; not a contractor quotation or tender price.',
        'Rates are user-supplied and are not verified market benchmarks.',
        'Quantities are user-supplied inputs; verify their linkage to the referenced geometry artifact.',
        'Exclusions, taxes, escalation, location factors, and scope completeness are not inferred.'])
