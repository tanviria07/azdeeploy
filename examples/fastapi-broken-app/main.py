from fastapi import FastAPI
import os

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/db")
def db_status():
    if not DATABASE_URL:
        return {"error": "DATABASE_URL not set"}
    return {"status": "connected"}
