from pydantic import BaseModel
from typing import List

class Validation(BaseModel):
    order: int
    selected_ids: List[int]
    method: str

class SearchOutput(BaseModel):
    validations: List[Validation]
