-- Users / Orders / Subscriptions

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_screen_chat_id INTEGER,
    last_screen_message_id INTEGER
);

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    tariff_code TEXT NOT NULL,
    price_rub INTEGER NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL, -- created/paid/canceled/expired
    provider_invoice_id TEXT,
    pay_url TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    paid_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    tariff_code TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT, -- NULL => forever
    status TEXT NOT NULL, -- active/expired/revoked
    order_id TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_expires ON orders(expires_at);

CREATE INDEX IF NOT EXISTS idx_subs_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subs_ends ON subscriptions(ends_at);