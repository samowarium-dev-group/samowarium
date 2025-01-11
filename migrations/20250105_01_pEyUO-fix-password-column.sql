-- fix-password-column
-- depends: 20250102_01_zl9cg-init

ALTER TABLE users DROP COLUMN samoware_password;
ALTER TABLE users ADD samoware_password bytea;
