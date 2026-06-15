import requests
import time
import os

BASE_URL = "http://localhost:8000/api/v1"

def run_test():
    print("Starting Apollo Lead Sourcing Test...")

    # 1. Signup / Login to get token
    print("1. Authenticating...")
    login_data = {
        "username": "test_e2e@gomarg.com",
        "password": "password123"
    }
    # Try login first
    res = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    
    if res.status_code == 400: # Not found, let's signup
        signup_data = {
            "email": "test_e2e@gomarg.com",
            "password": "password123",
            "first_name": "Test",
            "last_name": "User"
        }
        requests.post(f"{BASE_URL}/auth/signup", json=signup_data)
        res = requests.post(f"{BASE_URL}/auth/login", data=login_data)
        
    if res.status_code != 200:
        print(f"Login failed: {res.text}")
    res.raise_for_status()
    token = res.json()["access_token"]
    org_id = res.json()["user"]["organization_id"]
    print(f"   Authenticated! Org ID: {org_id}")

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(org_id)
    }

    # 2. Test Sourcing Pipeline
    print("2. Testing Apollo Sourcing Pipeline...")
    
    search_payload = {
        "page": 1,
        "per_page": 10
    }
    
    print(f"   Searching for: {search_payload}")
    sourcing_res = requests.post(f"{BASE_URL}/sourcing/apollo", headers=headers, json=search_payload)
    
    if sourcing_res.status_code == 200:
        data = sourcing_res.json()
        print(f"   Success! {data.get('message')}")
    else:
        print(f"   Failed: {sourcing_res.text}")

if __name__ == "__main__":
    run_test()
