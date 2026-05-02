-- Example setup on external PostgreSQL (run with appropriate privileges).
-- Step 1: create role (pick a strong password).
CREATE ROLE orders_app WITH LOGIN PASSWORD 'choose-a-strong-password';

-- Step 2: create database owned by that role.
CREATE DATABASE orders OWNER orders_app;

-- The API creates the `orders` table on startup if it does not exist.
-- Ensure pg_hba.conf and network paths allow the OpenShift cluster to reach this host.
