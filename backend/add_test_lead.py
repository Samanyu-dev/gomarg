import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.lead import Lead

engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def main():
    async with AsyncSessionLocal() as session:
        # Get the first lead to grab the organization_id
        result = await session.execute(select(Lead).limit(1))
        existing_lead = result.scalars().first()
        
        if not existing_lead:
            print("No existing leads found to copy organization_id from.")
            return

        org_id = existing_lead.organization_id

        # Create dummy lead
        dummy_lead = Lead(
            organization_id=org_id,
            email="test.dummy@example.com",
            first_name="Test",
            last_name="User",
            company="Test Corp Inc.",
            job_title="Chief Testing Officer",
            phone_number="555-0199",
            city="San Francisco",
            state="California",
            country="United States",
            industry="Software",
            status="new"
        )
        
        session.add(dummy_lead)
        await session.commit()
        print("✅ Added 'Test User (test.dummy@example.com)' to your database!")

if __name__ == "__main__":
    asyncio.run(main())
