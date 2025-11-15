from app.database.db import client

def get_db():
    try:
        yield client
    finally:
        client.close()