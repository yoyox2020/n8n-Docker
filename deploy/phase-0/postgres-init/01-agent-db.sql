-- Init script: berjalan sekali saat volume postgres pertama kali dibuat.
-- Membuat database terpisah untuk MST Agent Service.
-- Database n8n dibuat otomatis oleh POSTGRES_DB env var.

CREATE DATABASE agentdb;

-- Aktifkan pgvector di kedua database
\connect agentdb
CREATE EXTENSION IF NOT EXISTS vector;

\connect n8n
CREATE EXTENSION IF NOT EXISTS vector;
