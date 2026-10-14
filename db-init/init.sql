CREATE TABLE products (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    category    VARCHAR(100),
    price_paise BIGINT NOT NULL,
    stock       INTEGER NOT NULL DEFAULT 0,
    tags        TEXT[],
    image_url   VARCHAR(500),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE orders (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          VARCHAR(255) NOT NULL,
    razorpay_order_id   VARCHAR(255) UNIQUE,
    status              VARCHAR(50) NOT NULL DEFAULT 'pending',
    amount_paise        BIGINT NOT NULL,
    items               JSONB NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    session_id  VARCHAR(255) NOT NULL,
    event_type  VARCHAR(100) NOT NULL,
    actor       VARCHAR(50) NOT NULL, 
    payload     JSONB,
    reasoning   TEXT,
    outcome     VARCHAR(50),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE upi_mandates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          VARCHAR(255) NOT NULL,
    customer_id         VARCHAR(255), 
    token_id            VARCHAR(255),
    block_order_id      VARCHAR(255),
    max_amount_paise    BIGINT DEFAULT 1000000,
    status              VARCHAR(50) DEFAULT 'pending',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO products (name, description, category, price_paise, stock, tags, image_url) VALUES
-- Shoes (4 items)
('Nike Air Max 270', 'Lightweight running shoe with Air unit cushioning', 'shoes', 289900, 10, ARRAY['running','nike','sports'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Shoes'),
('Campus Hype', 'Budget casual sneaker for everyday wear', 'shoes', 149900, 20, ARRAY['casual','budget','sneaker'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Shoes'),
('Puma RS-X', 'Retro-inspired chunky running shoe', 'shoes', 219900, 8, ARRAY['running','puma','retro'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Shoes'),
('Adidas Ultraboost', 'Premium performance running shoe with Boost midsole', 'shoes', 449900, 5, ARRAY['running','adidas','premium'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Shoes'),

-- Electronics (4 items)
('boAt Airdopes 141', 'True wireless earbuds with 42h battery', 'electronics', 149900, 25, ARRAY['earbuds','wireless','boat'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Electronics'),
('boAt Rockerz 450', 'Over-ear wireless headphones with 40mm drivers', 'electronics', 129900, 15, ARRAY['headphones','wireless','boat'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Electronics'),
('Fire-Boltt Phoenix', 'Smart watch with SpO2, heart rate and 120+ sports modes', 'electronics', 179900, 12, ARRAY['smartwatch','fitness','fireboltt'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Electronics'),
('Ambrane 20000mAh PowerBank', 'Fast charging power bank with dual USB output', 'electronics', 99900, 30, ARRAY['powerbank','charging','ambrane'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Electronics'),

-- Bags (3 items)
('Wildcraft Laptop Bag', '15.6 inch laptop backpack with rain cover', 'bags', 149900, 18, ARRAY['laptop','backpack','wildcraft'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Bags'),
('American Tourister Casual Backpack', 'Lightweight daily use backpack 28L', 'bags', 119900, 22, ARRAY['backpack','casual','tourister'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Bags'),
('Skybags Gym Bag', 'Duffel gym bag with shoe compartment', 'bags', 89900, 14, ARRAY['gym','duffel','skybags'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Bags'),

-- Clothing (3 items)
('Allen Solly Polo T-Shirt', 'Cotton polo t-shirt for men, regular fit', 'clothing', 79900, 35, ARRAY['tshirt','polo','cotton'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Clothing'),
('Levi''s Denim Jacket', 'Classic trucker jacket in mid-wash denim', 'clothing', 329900, 6, ARRAY['jacket','denim','levis'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Clothing'),
('Peter England Formal Shirt', 'Slim fit cotton formal shirt, white', 'clothing', 119900, 20, ARRAY['shirt','formal','cotton'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Clothing'),

-- Books (3 items)
('Designing Data-Intensive Applications', 'Martin Kleppmann - distributed systems bible', 'books', 54900, 40, ARRAY['tech','distributed','oreilly'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Books'),
('Atomic Habits', 'James Clear - build good habits, break bad ones', 'books', 34900, 50, ARRAY['self-help','habits','bestseller'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Books'),
('System Design Interview Vol 1', 'Alex Xu - system design prep guide', 'books', 44900, 30, ARRAY['tech','interview','systemdesign'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Books'),

-- Accessories (3 items)
('Noise ColorFit Pro 4', 'Smartband with AMOLED display and GPS', 'accessories', 249900, 10, ARRAY['smartband','fitness','noise'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Accessories'),
('Portronics SoundDrum', 'Portable bluetooth speaker 10W with bass', 'accessories', 119900, 16, ARRAY['speaker','bluetooth','portable'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Accessories'),
('Croma USB-C Hub 7-in-1', 'Multi-port adapter with HDMI, USB 3.0, SD card', 'accessories', 199900, 12, ARRAY['usb','hub','adapter'], 'https://placehold.co/200x200/1a1a2e/e8e8f0?text=Accessories');
