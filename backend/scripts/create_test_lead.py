import asyncio
from uuid import UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from app.core.config import settings
from app.models.tenant import Organization
from app.models.lead import Lead

async def main():
    engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get first org
        org_res = await session.execute(select(Organization))
        org = org_res.scalars().first()
        if not org:
            print("No organization found.")
            return

        email = input("Enter your real email address to receive test campaigns: ")
        
        lead = Lead(
            organization_id=org.id,
            first_name="Test",
            last_name="User",
            email=email,
            company="GoMarg Testing",
            job_title="QA Tester",
            source="manual_test"
        )
        session.add(lead)
        await session.commit()
        print(f"✅ Success! Test lead '{email}' created.")
        print("Go to your Campaign -> Pipeline Queue, and you can now assign this lead to test your sequences.")

if __name__ == "__main__":
    asyncio.run(main())
