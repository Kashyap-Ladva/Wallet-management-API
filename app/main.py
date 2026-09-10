from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Wallet Management API"}


@app.get("/health")
def health():
    return {"status": "healthy"}