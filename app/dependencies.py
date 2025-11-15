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