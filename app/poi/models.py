from pydantic import BaseModel

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
    vector_embedding: list[float]
