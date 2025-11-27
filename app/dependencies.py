from typing import Annotated

from fastapi import Depends
from pymilvus import MilvusClient
from pathlib import Path


def get_db_gen():
    """
    Base function from
    https://www.getorchestra.io/guides/fastapi-and-sql-databases-a-detailed-tutorial\
    """

    client = MilvusClient(Path(Path.cwd(), "vectorDB.db").__str__())
    try:
        yield client
    finally:
        client.close()

def get_db():
    #return client
    ...

DbDep = Annotated[MilvusClient, Depends(get_db_gen)]
"""
Declares database dependency as an easy to use type.
Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-session-dependency
"""
