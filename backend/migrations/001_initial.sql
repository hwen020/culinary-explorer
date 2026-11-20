CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0,
    customer TEXT UNIQUE,
    plan TEXT NOT NULL DEFAULT 'free',
    subscription_status TEXT NOT NULL DEFAULT 'none'
);
CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    expires BIGINT NOT NULL
);
CREATE TABLE action_tokens (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    expires BIGINT NOT NULL
);
CREATE TABLE counters (
    scope TEXT NOT NULL,
    period BIGINT NOT NULL,
    count INTEGER NOT NULL,
    PRIMARY KEY (scope, period)
);
CREATE TABLE restaurants (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated BIGINT NOT NULL
);
CREATE TABLE favorites (
    user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    place_id TEXT NOT NULL,
    collection TEXT NOT NULL,
    PRIMARY KEY (user_id, place_id)
);
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created BIGINT NOT NULL
);
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    payload TEXT NOT NULL,
    created BIGINT NOT NULL
);
CREATE TABLE searches (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    created BIGINT NOT NULL
);
CREATE TABLE webhook_events (id TEXT PRIMARY KEY);
