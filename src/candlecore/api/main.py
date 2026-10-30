from fastapi import FastAPI

from candlecore.api.routes import health, market

app = FastAPI(title="CandleCore", version="0.1.0")

app.include_router(health.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"service": "CandleCore", "status": "ok"}
