from typing import Annotated

from fastapi import Depends, HTTPException
from pymilvus import MilvusClient
from pathlib import Path
import requests


def get_db_gen():
    """
    Base function from
    https://www.getorchestra.io/guides/fastapi-and-sql-databases-a-detailed-tutorial
    """

    client = MilvusClient(Path(Path.cwd(), "vectorDB.db").__str__())
    try:
        yield client
    finally:
        client.close()

NeedsDb = Annotated[MilvusClient, Depends(get_db_gen)]
"""
Declares database dependency as an easy to use type.
Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-session-dependency
"""

def needs_ollama():
    error = HTTPException(status_code=404, detail="""Ollama is not running!
            ensure ollama is running on the server before querying this route!""")
    try:
        res = requests.get("http://localhost:11434")
        if res.text != "Ollama is running":
            raise error
    except:
        raise error

NeedsOllama = Depends(needs_ollama)
