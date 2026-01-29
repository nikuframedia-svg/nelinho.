-- ProdPlan ONE - Initial Database Setup
-- Creates extensions and base schema

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create schemas for each module
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS plan;
CREATE SCHEMA IF NOT EXISTS profit;
CREATE SCHEMA IF NOT EXISTS hr;

-- Grant permissions
GRANT ALL ON SCHEMA core TO prodplan;
GRANT ALL ON SCHEMA plan TO prodplan;
GRANT ALL ON SCHEMA profit TO prodplan;
GRANT ALL ON SCHEMA hr TO prodplan;

-- Audit trigger function
CREATE OR REPLACE FUNCTION core.audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO core.audit_log (
            tenant_id, entity_type, entity_id, action, new_values, created_at
        ) VALUES (
            NEW.tenant_id,
            TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
            NEW.id,
            'INSERT',
            to_jsonb(NEW),
            NOW()
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO core.audit_log (
            tenant_id, entity_type, entity_id, action, old_values, new_values, created_at
        ) VALUES (
            NEW.tenant_id,
            TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
            NEW.id,
            'UPDATE',
            to_jsonb(OLD),
            to_jsonb(NEW),
            NOW()
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO core.audit_log (
            tenant_id, entity_type, entity_id, action, old_values, created_at
        ) VALUES (
            OLD.tenant_id,
            TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
            OLD.id,
            'DELETE',
            to_jsonb(OLD),
            NOW()
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Comment for documentation
COMMENT ON FUNCTION core.audit_trigger_func() IS 'Automatic audit logging for all tenant-scoped tables';










