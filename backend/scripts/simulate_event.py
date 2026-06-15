import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import desc
from app.core.config import settings
from app.models.email import Email

async def main():
    engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get the latest sent email
        result = await session.execute(
            select(Email).filter(Email.status == 'sent').order_by(desc(Email.created_at)).limit(1)
        )
        email_record = result.scalars().first()
        
        if not email_record:
            print("❌ No 'sent' emails found in the database. Send an email through a campaign first!")
            return
            
        print(f"Found latest sent email ID: {email_record.id}")
        print(f"Provider Message ID: {email_record.provider_message_id}")
        
        print("\nWhat event would you like to simulate?")
        print("1. opened")
        print("2. clicked")
        print("3. reply")
        print("4. hard_bounce")
        
        choice = input("Enter number (1-4): ")
        event_map = {"1": "opened", "2": "clicked", "3": "reply", "4": "hard_bounce"}
        event = event_map.get(choice, "opened")
        
        payload = {
            "event": event,
            "message-id": email_record.provider_message_id,
            "email": "test@example.com"
        }
        
        if event == "reply":
            reply_text = input("\nEnter reply text (e.g. 'I am interested!'): ")
            payload["subject"] = "Re: Hello"
            payload["body"] = reply_text
            
        print(f"\nSending webhook to local server: {payload}")
        
        async with httpx.AsyncClient() as client:
            response = await client.post("http://localhost:8000/api/v1/webhooks/brevo", json=payload)
            print(f"Server response: {response.status_code}")
            print(response.json())
            
            if response.status_code == 200:
                print("✅ Webhook processed successfully! Check your backend logs to see the Agent's reaction.")

if __name__ == "__main__":
    asyncio.run(main())
