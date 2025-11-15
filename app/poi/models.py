from typing import Optional, Any

from pydantic import BaseModel
from pymilvus.model.dense import OnnxEmbeddingFunction


class Pos(BaseModel):
    x: float
    y: float
    z: float

class POI(BaseModel):
    """
    Please keep up to date with the implementation of this! This is very subject
    to change once I learn more about how to data is structured. As of right now,
    this is based off the information in the shared doc from the first meeting.
    """
    id: str
    label: str
    tags: list[str]
    position: Pos
    description: str
    vector_embedding: Optional[list[float]]

    def generate_embedding(self, embedding_fn: OnnxEmbeddingFunction):
        embedding_str = f"label: {self.label} | "
        f"tags: {",".join(self.tags)} | "
        f"description: {self.description} | "

        embedding = embedding_fn.encode_documents([embedding_str])
        self.vector_embedding = embedding[0]
