import requests
import time
import os

BASE_URL = "http://localhost:8081/api/v1"

def run_test():
    print("Starting End-to-End Test...")

    # 1. Signup
    print("1. Testing Auth Signup...")
    signup_data = {
        "email": "test_e2e@gomarg.com",
        "password": "password123",
        "first_name": "Test",
        "last_name": "User",
        "organization_name": "GoMarg Test Org"
    }
    res = requests.post(f"{BASE_URL}/auth/signup", json=signup_data)
    if res.status_code not in (201, 400): # 400 if already exists
        print(f"Signup failed: {res.text}")
        return
    
    # 2. Login
    print("2. Testing Auth Login...")
    login_data = {
        "username": "test_e2e@gomarg.com",
        "password": "password123"
    }
    res = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if res.status_code != 200:
        print(f"Login failed: {res.text}")
        return
    token = res.json()["access_token"]
    org_id = res.json()["user"]["organization_id"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": org_id
    }
    
    # 3. Create a Lead manually (simulating import for a single lead)
    print("3. Testing Lead Creation...")
    lead_data = {
        "first_name": "Sam",
        "last_name": "Altman",
        "email": "sam@openai.com",
        "company": "OpenAI",
        "job_title": "CEO"
    }
    res = requests.post(f"{BASE_URL}/leads/", json=lead_data, headers=headers)
    if res.status_code != 201:
        print(f"Lead creation failed: {res.text}")
        return
    lead_id = res.json()["id"]

    # 4. Generate AI Email
    print(f"4. Testing AI Email Generation for Lead {lead_id}...")
    gen_data = {"campaign_goal": "Sell our GoMarg AI SDR platform"}
    res = requests.post(f"{BASE_URL}/generate/email/{lead_id}", json=gen_data, headers=headers)
    if res.status_code != 200:
        print(f"Email Generation failed (Is GEMINI_API_KEY valid?): {res.text}")
        return
    email_output = res.json()
    print("   AI Output generated successfully!")
    print(f"   Subject: {email_output['subject']}")
    
    # 5. Simulate Reply
    print("5. Testing Reply Simulation (Sentiment Analysis)...")
    reply_data = {
        "lead_id": lead_id,
        "email_text": "This sounds really interesting. Let's book a call for next Tuesday."
    }
    res = requests.post(f"{BASE_URL}/webhooks/replies/simulate", json=reply_data, headers=headers)
    if res.status_code != 200:
        print(f"Reply simulation failed: {res.text}")
        return
    analysis = res.json()
    print(f"   Analysis Output: {analysis}")

    # 6. Verify Lead Status
    print("6. Verifying Lead Status was updated...")
    res = requests.get(f"{BASE_URL}/leads/{lead_id}", headers=headers)
    lead_status = res.json()["status"]
    print(f"   Final Lead Status: {lead_status}")

    if lead_status == "Qualified":
        print("\n✅ E2E TEST PASSED! The core system is fully operational.")
    else:
        print("\n❌ E2E TEST FAILED: Lead status did not update to Qualified.")

if __name__ == "__main__":
    run_test()
