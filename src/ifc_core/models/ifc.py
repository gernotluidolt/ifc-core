from pydantic import BaseModel
from typing import Optional


class ModelMetadata(BaseModel):
    schema_version: str
    author: str
    timestamp: str


class ModificationResult(BaseModel):
    success: bool
    msg: str
    express_id: Optional[int] = None
