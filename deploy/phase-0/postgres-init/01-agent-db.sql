-- Init script: berjalan sekali saat volume postgres pertama kali dibuat.
-- Membuat database terpisah untuk MST Agent Service.
-- Database n8n dibuat otomatis oleh POSTGRES_DB env var.

CREATE DATABASE agentdb;
