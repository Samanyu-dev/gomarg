import httpx
import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv("/Users/apple/Desktop/projects/gomarg/backend/.env")

async def test_apollo():
    api_key = os.getenv("APOLLO_API_KEY")
    search_url = "https://api.apollo.io/v1/mixed_people/search"
    payload = {
        "page": 1,
        "per_page": 2,
        "q_keywords": "Data Engineering",
        "q_organization_name": "Optum",
    }
    
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": api_key
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(search_url, headers=headers, json=payload, timeout=30.0)
        print("Status:", response.status_code)
        if response.status_code == 200:
            data = response.json()
            people = data.get("people", [])
            print(f"Found {len(people)} people.")
        else:
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test_apollo())
