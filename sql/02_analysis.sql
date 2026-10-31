-- GLP-1 market and prescriber analysis, Medicare Part D 2023-2024
-- MySQL 8.0+ (CTEs, window functions). Runs on the table built by 01_schema_load.sql.
--   mysql -u root -p --table partd < sql/02_analysis.sql
-- Ranking functions break ties on npi so results are identical on every MySQL/MariaDB install.
-- Each query is tagged "-- name: <x>"; src/run_analysis.py saves each result to outputs/tables/<x>.csv

USE partd;

-- name: data_quality
-- Why we size on claims: CMS blanks beneficiary counts under 11, and drops any
-- prescriber-drug row with fewer than 11 claims (min_claims should be 11).
SELECT yr,
       COUNT(*)                     AS rows_,
       MIN(clms)                    AS min_claims,
       ROUND(AVG(benes IS NULL), 3) AS share_benes_suppressed
FROM rx GROUP BY yr ORDER BY yr;

-- name: market_size
SELECT yr,
       SUM(clms)                AS claims,
       ROUND(SUM(cost) / 1e9, 2) AS gross_cost_bn_usd,
       COUNT(DISTINCT npi)      AS prescribers
FROM rx GROUP BY yr ORDER BY yr;

-- name: molecule_share
SELECT yr, molecule,
       SUM(clms) AS claims,
       ROUND(SUM(clms) / SUM(SUM(clms)) OVER (PARTITION BY yr), 4) AS claim_share,
       ROUND(SUM(cost) / SUM(clms), 0) AS cost_per_claim_usd,
       COUNT(DISTINCT npi) AS prescribers
FROM rx GROUP BY yr, molecule ORDER BY yr, claims DESC;

-- name: brand_split_2024
-- Wegovy and Zepbound barely appear: Part D cannot cover drugs used for weight loss,
-- so this data describes the type 2 diabetes GLP-1 market.
SELECT brand, molecule, SUM(clms) AS claims
FROM rx WHERE yr = '2024' GROUP BY brand, molecule ORDER BY claims DESC;

-- name: prescriber_deciles_2024
WITH p AS (
  SELECT npi, SUM(clms) AS c FROM rx WHERE yr = '2024' GROUP BY npi
), r AS (
  SELECT npi, c, NTILE(10) OVER (ORDER BY c DESC, npi) AS decile FROM p
)
SELECT decile,
       COUNT(*) AS prescribers,
       MIN(c)   AS min_claims,
       SUM(c)   AS claims,
       ROUND(SUM(c) / (SELECT SUM(c) FROM p), 4) AS claim_share
FROM r GROUP BY decile ORDER BY decile;

-- name: specialty_mix_2024
SELECT specialty,
       SUM(clms) AS claims,
       COUNT(DISTINCT npi) AS prescribers,
       ROUND(SUM(clms) / COUNT(DISTINCT npi), 0) AS claims_per_prescriber,
       ROUND(SUM(clms) / (SELECT SUM(clms) FROM rx WHERE yr = '2024'), 4) AS claim_share
FROM rx WHERE yr = '2024'
GROUP BY specialty ORDER BY claims DESC LIMIT 12;

-- name: mounjaro_share_by_specialty
-- Is Mounjaro's rise led by specialists or spread across primary care?
SELECT yr, specialty,
       SUM(clms) AS glp1_claims,
       ROUND(SUM(CASE WHEN molecule = 'Tirzepatide' THEN clms ELSE 0 END) / SUM(clms), 4) AS mounjaro_share
FROM rx
WHERE specialty IN ('Family Practice','Internal Medicine','Nurse Practitioner','Endocrinology','Physician Assistant')
GROUP BY yr, specialty ORDER BY specialty, yr;

-- name: adoption_by_specialty_2024
-- Share of each specialty's GLP-1 prescribers with reportable Mounjaro volume (>=11 claims)
WITH p AS (
  SELECT npi, MAX(specialty) AS specialty, MAX(molecule = 'Tirzepatide') AS has_tirz
  FROM rx WHERE yr = '2024' GROUP BY npi
)
SELECT specialty, COUNT(*) AS prescribers, SUM(has_tirz) AS writing_mounjaro,
       ROUND(AVG(has_tirz), 4) AS adoption_rate
FROM p
WHERE specialty IN ('Family Practice','Internal Medicine','Nurse Practitioner','Endocrinology','Physician Assistant')
GROUP BY specialty ORDER BY adoption_rate DESC;

-- name: mounjaro_share_by_state_2024
-- States with >20K GLP-1 claims: all 50 states + DC + PR qualify; small territory and
-- military codes (GU, VI, MP, AE, AP) and unknown codes (XX, ZZ) fall below it
SELECT state,
       SUM(clms) AS glp1_claims,
       ROUND(SUM(CASE WHEN molecule = 'Tirzepatide' THEN clms ELSE 0 END) / SUM(clms), 4) AS mounjaro_share
FROM rx WHERE yr = '2024'
GROUP BY state HAVING SUM(clms) > 20000
ORDER BY mounjaro_share;

-- name: adoption_cohort
-- Prescribers active in both years: did they move onto Mounjaro?
-- ("no Mounjaro" = fewer than 11 Mounjaro claims, the CMS reporting floor)
WITH s AS (
  SELECT npi, yr, MAX(molecule = 'Tirzepatide') AS has_tirz
  FROM rx GROUP BY npi, yr
), both_yrs AS (
  SELECT a.npi, a.has_tirz AS tirz_2023, b.has_tirz AS tirz_2024
  FROM s a JOIN s b ON a.npi = b.npi AND a.yr = '2023' AND b.yr = '2024'
)
SELECT CASE WHEN tirz_2023 = 1 AND tirz_2024 = 1 THEN 'Kept Mounjaro'
            WHEN tirz_2023 = 0 AND tirz_2024 = 1 THEN 'Adopted in 2024'
            WHEN tirz_2023 = 1 AND tirz_2024 = 0 THEN 'Dropped below reporting floor'
            ELSE 'Still no Mounjaro' END AS status,
       COUNT(*) AS prescribers,
       ROUND(COUNT(*) / (SELECT COUNT(*) FROM both_yrs), 4) AS share
FROM both_yrs GROUP BY status ORDER BY prescribers DESC;

-- name: whitespace_2024
-- Prescribers with no reportable Mounjaro, split by GLP-1 volume quintile.
-- High-volume GLP-1 writers without Mounjaro are the clearest targets for a Mounjaro brand team.
WITH p AS (
  SELECT npi,
         SUM(clms) AS glp1_claims,
         MAX(molecule = 'Tirzepatide') AS has_tirz
  FROM rx WHERE yr = '2024' GROUP BY npi
), q AS (
  SELECT *, NTILE(5) OVER (ORDER BY glp1_claims DESC, npi) AS quintile FROM p
)
SELECT quintile,
       COUNT(*) AS prescribers,
       SUM(1 - has_tirz) AS no_mounjaro,
       ROUND(AVG(1 - has_tirz), 4) AS share_no_mounjaro,
       SUM(CASE WHEN has_tirz = 0 THEN glp1_claims ELSE 0 END) AS glp1_claims_of_no_mounjaro
FROM q GROUP BY quintile ORDER BY quintile;

-- name: whitespace_targets_by_specialty_2024
-- Top-quintile GLP-1 prescribers with no Mounjaro: who are they?
WITH p AS (
  SELECT npi, MAX(specialty) AS specialty,
         SUM(clms) AS glp1_claims,
         MAX(molecule = 'Tirzepatide') AS has_tirz
  FROM rx WHERE yr = '2024' GROUP BY npi
), q AS (
  SELECT *, NTILE(5) OVER (ORDER BY glp1_claims DESC, npi) AS quintile FROM p
)
SELECT specialty,
       COUNT(*) AS target_prescribers,
       SUM(glp1_claims) AS their_glp1_claims,
       ROUND(AVG(glp1_claims), 0) AS avg_glp1_claims
FROM q WHERE quintile = 1 AND has_tirz = 0
GROUP BY specialty ORDER BY target_prescribers DESC LIMIT 10;
