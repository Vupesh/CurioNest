-- CurioNest Dynamic Domain Configuration Schema

C-- ==============================
-- Lead System
-- ==============================

CREATE TYPE lead_status AS ENUM (
    'NEW',
    'QUALIFIED',
    'CONTACTED',
    'CONVERTED'
);

CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(100) NOT NULL,
    subject VARCHAR(100),
    chapter VARCHAR(100),
    question TEXT,

    escalation_code VARCHAR(100) NOT NULL,
    escalation_reason TEXT,

    confidence DOUBLE PRECISION NOT NULL,
    engagement_score DOUBLE PRECISION NOT NULL,
    intent_strength INT NOT NULL,

    status lead_status NOT NULL DEFAULT 'NEW',

    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_leads_session_id
ON leads(session_id);

-- ==============================
-- Lead Contacts
-- ==============================

CREATE TABLE lead_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,

    name TEXT,
    email TEXT,
    phone TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==============================
-- Lead Events
-- ==============================

CREATE TABLE lead_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    session_id VARCHAR(100),

    event_type TEXT,
    escalation_code TEXT,

    confidence DOUBLE PRECISION,
    engagement_score DOUBLE PRECISION,

    created_at TIMESTAMP DEFAULT now()
);