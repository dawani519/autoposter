-- Create tables for the auto-poster application

-- Niches table
CREATE TABLE IF NOT EXISTS niches (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    primary_statement TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Hashtags table
CREATE TABLE IF NOT EXISTS hashtags (
    id SERIAL PRIMARY KEY,
    niche_id INTEGER REFERENCES niches(id) ON DELETE CASCADE,
    tag VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Platform accounts table
CREATE TABLE IF NOT EXISTS platform_accounts (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    api_key TEXT,
    api_secret TEXT,
    access_token TEXT,
    access_secret TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Posts table
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    niche_id INTEGER REFERENCES niches(id) ON DELETE CASCADE,
    account_id INTEGER REFERENCES platform_accounts(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    media_url TEXT,
    scheduled_time TIMESTAMP,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schedule table
CREATE TABLE IF NOT EXISTS schedule (
    id SERIAL PRIMARY KEY,
    niche_id INTEGER REFERENCES niches(id) ON DELETE CASCADE,
    posts_per_day INTEGER NOT NULL,
    needs_approval INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_posts_niche_id ON posts(niche_id);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);
CREATE INDEX IF NOT EXISTS idx_posts_scheduled_time ON posts(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_hashtags_niche_id ON hashtags(niche_id);
CREATE INDEX IF NOT EXISTS idx_schedule_niche_id ON schedule(niche_id);
