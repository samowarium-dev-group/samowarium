-- fix-telegram-id
-- depends: 20250105_01_pEyUO-fix-password-column

ALTER TABLE users DROP CONSTRAINT users_pkey;
ALTER TABLE users DROP COLUMN telegram_id;
ALTER TABLE users ADD telegram_id bigint PRIMARY KEY;
