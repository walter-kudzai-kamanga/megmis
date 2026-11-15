# Data Model & Migrations

## PostgreSQL + PostGIS

Enable: CREATE EXTENSION postgis;

Tables (all tenant-scoped tables carry tenant_id uuid NOT NULL):
tenants(id pk, name, slug unique, plan, status, settings jsonb, created_at)
api_keys(id pk, tenant_id fk, hashed_key, prefix, scopes text[], label,
         last_used_at, expires_at, revoked_at)
locations(id pk, tenant_id, name, geom geometry(Point,4326), admin_area)
routes(id pk, tenant_id, origin_id, destination_id, waypoints jsonb, profile,
       vehicle_class, departure_time, result jsonb, created_at)
journeys(id pk, tenant_id, route_id, status, current_position geometry(Point,4326),
         monitored_route geometry(LineString,4326), alert_subscriptions jsonb,
         created_at, updated_at)
road_reports(id pk, tenant_id, location_id, type, severity, confidence, status,
             reporter_ref, evidence_refs jsonb, reported_at, expires_at,
             corroboration_count)
incidents(id pk, source, road_report_id, geom geometry(Geometry,4326), type,
          severity, confidence, valid_from, valid_to, status)
weather_snapshots(id pk, location_id, provider, observed_at, payload jsonb,
                  is_official_warning bool)
risk_assessments(id pk, tenant_id, subject_type, subject_id, activity, score,
                 level, indicators jsonb, recommendations jsonb, confidence,
                 data_sources text[])
agent_sessions(id pk, tenant_id, channel, state, transcript_ref, started_at,
               ended_at)
audit_log(id pk, tenant_id, actor, action, resource, request_id, ip, ts)

## Indexes
GiST on all geometry columns. B-tree on (tenant_id, created_at) for list queries.
Partial index on incidents where status='active'.

## RLS
ALTER TABLE ... ENABLE ROW LEVEL SECURITY;
Policy: tenant_isolation USING (tenant_id = current_setting('app.tenant_id')::uuid)
App DB role is non-superuser and non-BYPASSRLS.

## Redis
weather:{provider}:{lat}:{lon}:{bucket}  TTL 10m
route:{hash}:{profile}                   TTL 5m
ratelimit:{tenant}:{window}              TTL window
journey:{id}:state                       TTL 24h

## Object storage
s3://megmis/audio/{tenant}/{session}/{chunk}
s3://megmis/reports/{tenant}/{report}/evidence/{file}

## Migrations
Alembic. One migration per PR max. Seed script loads Zimbabwe test regions and a
small OSM extract for local routing graphs.

## Retention
incidents: expire per type (pothole 30d, closure until cleared)
audit_log: 400 days
audio: 90 days unless tenant opt-in