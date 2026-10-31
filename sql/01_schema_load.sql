-- Schema + load for the CMS Part D GLP-1 extract
-- MySQL 8.0+. Run from the repo root (the CSV path is relative to where the client runs):
--   mysql --local-infile=1 -u root -p < sql/01_schema_load.sql
-- The server must allow local loads once: SET GLOBAL local_infile = 1;

CREATE DATABASE IF NOT EXISTS partd;
USE partd;

DROP TABLE IF EXISTS rx;
CREATE TABLE rx (
  npi        VARCHAR(10)   NOT NULL,  -- prescriber National Provider Identifier
  last_name  VARCHAR(100),
  first_name VARCHAR(100),
  city       VARCHAR(60),
  state      VARCHAR(4),
  state_fips VARCHAR(4),
  specialty  VARCHAR(80),             -- Prscrbr_Type
  spec_src   VARCHAR(40),
  brand      VARCHAR(60),
  molecule   VARCHAR(60),             -- generic name
  clms       INT,                     -- total claims (fills incl. refills)
  fills      DECIMAL(12,1),           -- standardised 30-day fills
  day_supply INT,
  cost       DECIMAL(14,2),           -- gross drug cost, USD, before rebates
  benes      INT NULL,                -- unique beneficiaries; NULL when CMS suppresses (<11)
  yr         CHAR(4)       NOT NULL,
  KEY idx_yr_mol (yr, molecule),
  KEY idx_npi (npi)
);

-- The 7 GE65_* (age 65+) columns are read into throwaway variables
LOAD DATA LOCAL INFILE 'data/partd_glp1_2023_2024.csv'
INTO TABLE rx
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(npi, last_name, first_name, city, state, state_fips, specialty, spec_src, brand, molecule,
 clms, fills, day_supply, cost, @benes, @s1, @s2, @s3, @s4, @s5, @s6, @s7, @yr)
SET benes = NULLIF(@benes, ''), yr = TRIM(TRAILING '\r' FROM @yr);

-- Load check: expect 752,159 rows (337,749 for 2023, 414,410 for 2024)
SELECT yr, COUNT(*) AS rows_loaded FROM rx GROUP BY yr;
