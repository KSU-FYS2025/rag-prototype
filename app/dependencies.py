from typing import Annotated

from fastapi import Depends
from pymilvus import MilvusClient

from app.database.db import client


def get_db():
    """
    Base function from
    https://www.getorchestra.io/guides/fastapi-and-sql-databases-a-detailed-tutorial\
    """
    try:
        yield client
    finally:
        client.close()

DbDep = Annotated[MilvusClient, Depends(get_db)]
"""
Declares database dependency as an easy to use type.
Reference: https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-session-dependency
"""
