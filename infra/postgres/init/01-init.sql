-- Runs once, on first start of an empty volume.
CREATE DATABASE phoenix;
\connect sahayak
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;
