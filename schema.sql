-- AutoPoster schema (PostgreSQL). For reference only: the app creates and upgrades
-- its tables automatically on startup (see autoposter/db.py).

CREATE TABLE niches (
	id SERIAL NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	primary_statement TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE platform_accounts (
	id SERIAL NOT NULL, 
	platform VARCHAR(50) NOT NULL, 
	name VARCHAR(255), 
	author_urn VARCHAR(255), 
	api_key TEXT, 
	api_secret TEXT, 
	access_token TEXT, 
	access_secret TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE hashtags (
	id SERIAL NOT NULL, 
	niche_id INTEGER NOT NULL, 
	tag VARCHAR(255) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(niche_id) REFERENCES niches (id) ON DELETE CASCADE
);


CREATE TABLE posts (
	id SERIAL NOT NULL, 
	niche_id INTEGER, 
	account_id INTEGER, 
	content TEXT NOT NULL, 
	media_url TEXT, 
	scheduled_time TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(50) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	attempts INTEGER NOT NULL, 
	last_error TEXT, 
	posted_at TIMESTAMP WITHOUT TIME ZONE, 
	external_id VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(niche_id) REFERENCES niches (id) ON DELETE CASCADE, 
	FOREIGN KEY(account_id) REFERENCES platform_accounts (id) ON DELETE CASCADE
);

CREATE INDEX ix_posts_scheduled_time ON posts (scheduled_time);
CREATE INDEX ix_posts_status ON posts (status);

CREATE TABLE schedule (
	id SERIAL NOT NULL, 
	niche_id INTEGER NOT NULL, 
	account_id INTEGER, 
	posts_per_day INTEGER NOT NULL, 
	needs_approval INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(niche_id) REFERENCES niches (id) ON DELETE CASCADE, 
	FOREIGN KEY(account_id) REFERENCES platform_accounts (id) ON DELETE SET NULL
);

