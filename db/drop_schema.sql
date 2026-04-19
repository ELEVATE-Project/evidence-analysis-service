-- Drop tables in reverse order (for cleanup/reset)
DROP TABLE IF EXISTS executions CASCADE;
DROP TABLE IF EXISTS csv_source_types CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Drop extensions
DROP EXTENSION IF EXISTS "uuid-ossp";
