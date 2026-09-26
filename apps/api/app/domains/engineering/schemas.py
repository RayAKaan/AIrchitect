from pydantic import BaseModel,Field,model_validator

class RateEntryIn(BaseModel):
 item_code:str=Field(min_length=1,max_length=80)
 category:str=Field(min_length=1,max_length=80)
 description:str=Field(min_length=1,max_length=240)
 quantity_code:str=Field(min_length=1,max_length=80)
 unit:str=Field(pattern="^(m|m2|m3|kg|count|ratio)$")
 rate:float=Field(gt=0)
 low_rate:float|None=Field(default=None,gt=0)
 high_rate:float|None=Field(default=None,gt=0)
 source_reference:str=Field(min_length=1,max_length=500)
 effective_date:str=Field(min_length=4,max_length=40)
 confidence:str="USER_DECLARED"
 @model_validator(mode="after")
 def bounds(self):
  if self.low_rate is not None and self.low_rate>self.rate:raise ValueError("low_rate cannot exceed rate")
  if self.high_rate is not None and self.high_rate<self.rate:raise ValueError("high_rate cannot be below rate")
  return self
class RateScheduleCreate(BaseModel):
 organization_id:str
 name:str=Field(min_length=1,max_length=120)
 version:str=Field(min_length=1,max_length=40)
 jurisdiction:str=Field(min_length=1,max_length=120)
 currency:str=Field(default="SAR",pattern="^[A-Z]{3}$")
 source_reference:str=Field(min_length=1,max_length=500)
 effective_date:str=Field(min_length=4,max_length=40)
 source_type:str=Field(default="USER_PROVIDED",pattern="^(USER_PROVIDED|DEMO|VERIFIED_EXTERNAL)$")
 entries:list[RateEntryIn]=Field(min_length=1,max_length=100)
class EngineeringCalculateRequest(BaseModel):
 rate_schedule_id:str|None=None
