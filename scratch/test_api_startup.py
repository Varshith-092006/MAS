import asyncio
import httpx
from mas.api.main import app

async def check():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.get("/health")
        print("API Health Status:", r1.status_code, r1.json())
        r2 = await client.get("/proxy/health")
        print("Proxy Health Status:", r2.status_code, r2.json())
        r3 = await client.get("/runs")
        print("Runs API Status:", r3.status_code, "items:", len(r3.json()))
        r4 = await client.get("/evaluations/srdd-tasks")
        print("SRDD Tasks Status:", r4.status_code, "items:", len(r4.json()))

if __name__ == "__main__":
    asyncio.run(check())
