# GoMarg: AI Sales Automation Platform 🚀

Welcome to **GoMarg**, a next generation B2B sales automation platform. GoMarg bridges the gap between massive data sourcing and hyper personalized outreach. By integrating seamlessly with Apollo for lead data and leveraging advanced LLMs (Large Language Models) for email drafting, GoMarg acts as a fully autonomous AI sales agent.

---

## 🏗 System Architecture

GoMarg employs a decoupled, highly scalable architecture. The frontend is built on Next.js 16 (App Router) for a lightning fast, SEO friendly user experience, while the backend is powered by FastAPI (Python) for asynchronous, high performance data processing and AI integration.

```mermaid
graph TD
    subgraph Frontend [Client Side UI]
        Next[Next.js 16 App]
        Context[React AuthContext]
        Tailwind[Tailwind CSS v4]
    end

    subgraph Backend [FastAPI Server]
        Auth[Auth Router & JWT]
        Sourcing[Apollo Sourcing Engine]
        AI[AI Generation Service]
        ORM[SQLAlchemy ORM]
    end

    subgraph Infrastructure [Data & External]
        DB[(PostgreSQL Database)]
        Apollo((Apollo API))
        LLM((Gemini LLM))
    end

    Next -- "REST/JSON" --> Auth
    Next -- "REST/JSON" --> Sourcing
    Next -- "REST/JSON" --> AI
    
    Auth --> ORM
    Sourcing --> ORM
    AI --> ORM
    
    ORM --> DB
    Sourcing -- "HTTP POST" --> Apollo
    AI -- "Prompt/JSON" --> LLM
```

---

## 🎨 Interactive Elements & User Interface

The GoMarg dashboard is designed with a premium, hyper modern aesthetic focusing on user engagement and seamless workflow.

- **Glassmorphism Design:** Elements utilize translucent, frosted glass backgrounds (`backdrop-blur`) over subtle, dynamic animated gradients to create depth.
- **Dynamic Data Tables:** The Sourcing Page features a real time table populated by the backend. Empty states provide clear calls to action, while populated states offer instant search capabilities.
- **Micro Animations:** Form submissions, button clicks, and page transitions use `framer-motion` and Tailwind transitions to feel responsive and alive.
- **Real Time Feedback:** Using `reacthot-toast`, every action (saving a lead, authenticating, triggering the AI) provides instant, styled popup notifications to the user.
- **The "Sync Apollo Contacts" Trigger:** A visually distinct button that acts as the bridge between the UI and the asynchronous backend sourcing pipeline.

---

## 🔐 Authentication Flow & Tenant Isolation

Security and data privacy are paramount. GoMarg utilizes a strict Organization based multi tenant architecture. Every user belongs to an Organization, and all data queries are scoped to that Organization.

```mermaid
sequenceDiagram
    participant User
    participant NextJS
    participant FastAPI
    participant Postgres
    
    User->>NextJS: Submits Email & Password
    NextJS->>FastAPI: POST /api/v1/auth/login
    FastAPI->>Postgres: Verify User & Hash
    Postgres-->>FastAPI: User Data
    FastAPI->>Postgres: Fetch Organization ID
    Postgres-->>FastAPI: Organization UUID
    FastAPI-->>NextJS: Returns JWT + Org ID
    NextJS->>NextJS: Stores in localStorage & AuthContext
    NextJS->>User: Redirects to /dashboard
```

**Key Mechanisms:**
1. **JWT Encoding:** Passwords are hashed using `bcrypt`. A JWT is generated containing the user's ID.
2. **Interceptors:** The frontend `Axios` client intercepts every request to attach the `Authorization: Bearer <token>` and `X-Organization-ID` headers.
3. **Backend Middleware:** Every protected route dependency (`get_current_user`) verifies the JWT signature and ensures the user has access to the provided `X-Organization-ID`.

---

## 🔄 Apollo Sync Pipeline

GoMarg bypasses the tedious process of uploading CSVs. Instead, users browse Apollo's 250M+ database natively, save the contacts they like, and GoMarg pulls them directly via the API.

```mermaid
flowchart LR
    A[Click 'Sync Contacts'] --> B(FastAPI Endpoint)
    B --> C{Apollo API}
    C -- "HTTP POST /v1/contacts/search" --> C
    C --> D[Extract Contact Metadata]
    D --> E{Deduplication Check}
    E -- "Exists" --> F[Skip]
    E -- "New" --> G[Insert into 'leads' table]
    G --> H[Insert Raw JSON into 'research_documents']
    H --> I[Return Success to UI]
```

**Detailed Explanation:**
- **Endpoint:** Uses `/api/v1/sourcing/apollo`.
- **Data Capture:** Extracts First Name, Last Name, Email, Job Title, Company, and LinkedIn URL.
- **Research Seeding:** The raw JSON returned by Apollo is saved to a specialized `research_documents` table. This preserves all niche data points (like company size, industry, location) for the AI to analyze later, without bloating the main `leads` relational table.

---

## 🧠 AI Agent Architecture (The Brain)

The core value of GoMarg is the AI Agent that reads the sourced data and writes personalized emails. This is not a "mail merge template." It is a dynamic prompt-engineering pipeline.

```mermaid
sequenceDiagram
    participant UI as Frontend
    participant Svc as EmailGenerationService
    participant DB as PostgreSQL
    participant LLM as Gemini API
    
    UI->>Svc: Trigger Campaign for Lead X
    Svc->>DB: Fetch Lead Details
    Svc->>DB: Fetch all ResearchDocuments for Lead X
    DB-->>Svc: Returns Raw Apollo JSON & Scraping Data
    Svc->>Svc: Synthesize Context string
    Svc->>LLM: Send System Prompt + Sourced Context
    LLM-->>Svc: Return dynamically generated Email
    Svc->>DB: Save Email (Status: Draft)
    Svc-->>UI: Display Draft to User
```

**How the AI Prompting Works:**
1. **Context Aggregation:** The backend pulls all `ResearchDocument` records tied to the Lead.
2. **Prompt Assembly:** The `EmailGenerationService` builds a large prompt: 
   *"You are an elite sales SDR. Here is the data on the prospect: [Inject Sourced Data]. Here is our product: [Inject Campaign details]. Write a highly personalized 4-sentence cold email."*
3. **Execution:** The LLM processes the unstructured data, notes specific nuances (like the prospect's exact job title or company focus), and weaves them naturally into the email body.

---

## 🚀 How to Use / Getting Started

### Local Development Setup

#### 1. Start the Database Infrastructure
Ensure Docker is running, then spin up the Postgres container:
```bash
docker-compose up -d postgres
```

#### 2. Start the FastAPI Backend
The backend runs on Python 3.9+.
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*API Documentation will be available at `http://localhost:8000/docs`*

#### 3. Start the Next.js Frontend
```bash
cd frontend
npm run dev
```
*The Dashboard will be available at `http://localhost:3000`*

### Environment Variables
You must configure your `.env` file in the `backend/` directory:
```env
# Database
DATABASE_URL=postgresql://gomarg:gomarg_password@localhost:5432/gomarg_db

# Security
JWT_SECRET=your_super_secret_key

# External Services
APOLLO_API_KEY=your_apollo_api_key
GEMINI_API_KEY=your_llm_api_key
```

---

## 💻 Useful Developer Commands

**Database Management:**
- **Access Postgres Console:**
  ```bash
  docker exec -it gomarg-postgres-1 psql -U gomarg -d gomarg_db
  ```
- **Reset/Wipe Database:**
  ```bash
  cd backend && python test_db.py
  ```
- **Run Database Migrations (Alembic):**
  ```bash
  cd backend && alembic upgrade head
  ```

**Frontend Commands:**
- **Lint Code:** `npm run lint`
- **Build Production Bundle:** `npm run build`
- **Clear Next.js Cache:** `rm -rf .next`




//todo
now : keyword + company name -> director -> cxo-> all( go from seniority)
now : keywords for brightdata, data related jobs
later : utm-headers endpoint analytics
target : 1k/week ( showcase 1000 leads by this week) 
         3rd week of next month : 500-600 leads per day
         by end of this month : send mail to (new) 1000 leads + follow ups (atleast 200) 