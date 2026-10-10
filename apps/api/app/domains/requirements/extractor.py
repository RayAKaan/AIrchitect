from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Protocol
@dataclass(frozen=True)
class RequirementCandidate:
    category: str
    parameter: str
    raw_value: Any
    normalized_value: Any
    unit: str | None
    source_text: str
    value_type: str
    confidence: float
    extraction_method: str = "deterministic_pattern_v3"
class RequirementExtractor(Protocol):
    def extract(self, brief: str) -> list[RequirementCandidate]: ...
class DeterministicRequirementExtractor:
    """Conservative extractor: exact facts only, with context-aware ambiguity guards."""
    _quantity_units = r"(?:m2|m²|sqm|sq\.?\s*m|square\s*met(?:er|re)s?)"
    @staticmethod
    def _excluded_by_context(brief: str, match: re.Match[str]) -> bool:
        prefix = brief[max(0, match.start()-64):match.start()]
        prefix = re.split(r"[.!?;\n]", prefix)[-1].lower()
        patterns = (
            r"\b(?:no more than|not more than|up to|at most|less than|fewer than|under|below|maximum(?: of)?|minimum(?: of)?|at least|no fewer than|no less than|more than|greater than|over|above|between)\s*$",
            r"\b(?:do not|don't|does not|doesn't|must not|mustn't)\s+(?:[a-z]+\s+){0,2}$",
            r"\b(?:no|not|without|exclude|excludes|excluded|excluding|avoid|avoids|avoided|avoiding)\s+(?:(?:any|the|a|an|use|include|including|provide|require|requires|want|need)\s+){0,2}$",
        )
        return any(re.search(pattern,prefix,re.I) for pattern in patterns)
    def extract(self, brief: str) -> list[RequirementCandidate]:
        candidates: list[RequirementCandidate] = []
        def add(category: str, parameter: str, match: re.Match[str], value: Any, unit: str | None, value_type: str, confidence: float=1.0) -> None:
            if self._excluded_by_context(brief,match): return
            candidates.append(RequirementCandidate(category,parameter,match.group(1),value,unit,match.group(0),value_type,confidence))
        number_words={"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,"seven":7,"eight":8,"nine":9,"ten":10,"eleven":11,"twelve":12}
        floor_pattern=r"\b(\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)[ -]*(?:floors?|storeys?|stories)\b"
        for match in re.finditer(floor_pattern,brief,re.I):
            raw=match.group(1).lower()
            add("floor","floor_count",match,number_words.get(raw,int(raw) if raw.isdigit() else 0),"count","integer")
        site_patterns=[
            rf"\b(?:site|plot)(?:\s+area)?\s*(?:(?:is|of|:|=)\s*)?(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})",
            rf"\b(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})\s+(?:site|plot)(?:\s+area)?\b",
        ]
        for pattern in site_patterns:
            for match in re.finditer(pattern,brief,re.I):
                add("site","site_area",match,float(match.group(1).replace(",","")),"m2","decimal")
        gfa_patterns=[
            rf"\b(?:target\s+|approximately\s+|approx\.?\s+)?(?:gfa|gross floor area)\s*(?:of|:|=)?\s*(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})",
            rf"\b(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})\s*(?:target\s+)?(?:gfa|gross floor area)\b",
        ]
        for pattern in gfa_patterns:
            for match in re.finditer(pattern,brief,re.I):
                add("area","target_gfa",match,float(match.group(1).replace(",","")),"m2","decimal")
        if (not any(c.parameter=="target_gfa" for c in candidates)
            and not any(c.parameter=="site_area" for c in candidates)
            and not re.search(r"\b(?:site|plot)\b",brief,re.I)):
            area_matches=list(re.finditer(rf"\b(\d[\d,]*(?:\.\d+)?)\s*({self._quantity_units})\b",brief,re.I))
            if len(area_matches)==1:
                match=area_matches[0]
                add("area","target_gfa",match,float(match.group(1).replace(",","")),"m2","decimal",.8)
        for match in re.finditer(r"(?:floor[- ]to[- ]floor|floor height)[^\d]{0,20}(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\b",brief,re.I):
            add("height","floor_to_floor_height",match,float(match.group(1)),"m","decimal")
        for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\s*(?:high|height)\b",brief,re.I):
            add("height","building_height",match,float(match.group(1)),"m","decimal")
        for match in re.finditer(r"\b(?:building|overall)\s+height\s*(?:of|is|:|=)?\s*(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\b",brief,re.I):
            add("height","building_height",match,float(match.group(1)),"m","decimal")
        for city in ("Riyadh","Jeddah","Dammam","Mecca","Medina","Bengaluru"):
            match=re.search(rf"\b({re.escape(city)})\b",brief,re.I)
            if match:
                add("location","city",match,city,None,"string");break
        use_match=re.search(r"\b(commercial\s+retail|retail|commercial|office)\b",brief,re.I)
        if use_match:
            normalized="commercial_retail" if "retail" in use_match.group(1).lower() else use_match.group(1).lower()
            add("use","building_use",use_match,normalized,None,"enum")
        for parking_match in re.finditer(r"\b(basement|surface|podium)\s+parking\b",brief,re.I):
            add("parking","parking_arrangement",parking_match,parking_match.group(1).lower(),None,"enum")
        for match in re.finditer(r"\b(\d{1,5})\s*(?:parking\s+)?spaces\b",brief,re.I):
            add("parking","parking_spaces",match,int(match.group(1)),"count","integer")
        for match in re.finditer(r"\b(?:SAR|﷼)\s*([\d,]+(?:\.\d+)?)\b",brief,re.I):
            add("budget","budget",match,float(match.group(1).replace(",","")),"SAR","decimal")
        unique={}
        for c in candidates: unique[(c.parameter,str(c.normalized_value),c.source_text.lower())]=c
        return sorted(unique.values(),key=lambda c:(c.parameter,c.source_text.lower()))
