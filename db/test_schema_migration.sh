#!/bin/bash
# Smoke test for db/schema.sql idempotency and required Execution schema fields.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA_FILE="$ROOT_DIR/db/schema.sql"

if [ -z "${DATABASE_URL:-}" ] && [ -f "$ROOT_DIR/.env" ]; then
    DATABASE_URL="$(grep -E '^DATABASE_URL=' "$ROOT_DIR/.env" | head -n 1 | cut -d '=' -f 2-)"
fi

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL is not set. Configure it in environment or .env."
    exit 1
fi

DB_NAME="$(echo "$DATABASE_URL" | sed -n 's#.*/\([^?]*\).*$#\1#p')"
if [ -z "$DB_NAME" ]; then
    echo "ERROR: Could not parse DB name from DATABASE_URL."
    exit 1
fi

BASE_URL="$(echo "$DATABASE_URL" | sed "s#/$DB_NAME#/postgres#")"
TEST_DB_NAME="${DB_NAME}_schema_smoke"
TEST_DB_URL="$(echo "$DATABASE_URL" | sed "s#/$DB_NAME#/$TEST_DB_NAME#")"

cleanup() {
    psql "$BASE_URL" -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$TEST_DB_NAME\";" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Preparing smoke test database: $TEST_DB_NAME"
psql "$BASE_URL" -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$TEST_DB_NAME\";"
psql "$BASE_URL" -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$TEST_DB_NAME\";"

echo "Applying schema (pass 1)"
psql "$TEST_DB_URL" -v ON_ERROR_STOP=1 -f "$SCHEMA_FILE" >/dev/null

echo "Applying schema (pass 2, idempotency check)"
psql "$TEST_DB_URL" -v ON_ERROR_STOP=1 -f "$SCHEMA_FILE" >/dev/null

assert_column_exists() {
    local column_name="$1"
    local exists
    exists="$(psql "$TEST_DB_URL" -At -v ON_ERROR_STOP=1 -c "
        SELECT EXISTS(
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'executions'
              AND column_name = '$column_name'
        );
    ")"

    if [ "$exists" != "t" ]; then
        echo "ERROR: Missing required column executions.$column_name"
        exit 1
    fi
}

assert_index_exists() {
    local index_name="$1"
    local exists
    exists="$(psql "$TEST_DB_URL" -At -v ON_ERROR_STOP=1 -c "
        SELECT EXISTS(
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'executions'
              AND indexname = '$index_name'
        );
    ")"

    if [ "$exists" != "t" ]; then
        echo "ERROR: Missing required index $index_name"
        exit 1
    fi
}

echo "Validating required execution columns"
required_columns=(
    tenant_code
    organization_code
    input_file_url
    input_file_size
    criterias_file_url
    criterias_file_size
    output_file_url
    output_file_size
    worker_id
    error_logs
    retry_count
    checkpoint_data
    upload_completed_at
    processing_started_at
    processing_completed_at
    average_processing_time
    estimated_time_seconds
    notification_sent
    notification_sent_at
    district
)

for column in "${required_columns[@]}"; do
    assert_column_exists "$column"
done

echo "Validating required execution indexes"
required_indexes=(
    idx_executions_created_by
    idx_executions_status
    idx_executions_created_at
    idx_executions_notification
)

for index_name in "${required_indexes[@]}"; do
    assert_index_exists "$index_name"
done

echo "Running execution metadata persistence smoke check"
psql "$TEST_DB_URL" -v ON_ERROR_STOP=1 -c "
    INSERT INTO executions (
        tenant_code,
        organization_code,
        name,
        status,
        created_by,
        criterias_file_size,
        retry_count,
        notification_sent
    )
    VALUES (
        'default',
        'default_code',
        'schema_smoke_execution',
        'queued',
        'smoke-user',
        1024,
        1,
        FALSE
    );

    UPDATE executions
    SET status = 'running',
        worker_id = 'worker-smoke',
        checkpoint_data = '{\"stage\": \"smoke\"}'::jsonb,
        processing_started_at = NOW()
    WHERE name = 'schema_smoke_execution';

    UPDATE executions
    SET status = 'completed',
        average_processing_time = 1.23,
        notification_sent = TRUE,
        notification_sent_at = NOW(),
        processing_completed_at = NOW(),
        completed_at = NOW()
    WHERE name = 'schema_smoke_execution';
" >/dev/null

smoke_result="$(psql "$TEST_DB_URL" -At -v ON_ERROR_STOP=1 -c "
    SELECT criterias_file_size::text || '|' || status || '|' || notification_sent::text
    FROM executions
    WHERE name = 'schema_smoke_execution'
    ORDER BY created_at DESC
    LIMIT 1;
")"

if [ "$smoke_result" != "1024|completed|true" ]; then
    echo "ERROR: Persistence smoke check failed (result: $smoke_result)"
    exit 1
fi

echo "Schema migration smoke test passed."
