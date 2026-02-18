-- ══════════════════════════════════════════════════════════════════════
-- VizGenie - PostgreSQL initialisation script
-- Creates sample sales_data table and loads fixture data
-- ══════════════════════════════════════════════════════════════════════

-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- Fuzzy text search
CREATE EXTENSION IF NOT EXISTS btree_gin; -- GIN index support

-- ── sales_data ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sales_data (
    "ORDERNUMBER"      INTEGER,
    "QUANTITYORDERED"  INTEGER,
    "PRICEEACH"        NUMERIC(10, 2),
    "ORDERLINENUMBER"  INTEGER,
    "SALES"            NUMERIC(10, 2),
    "ORDERDATE"        TIMESTAMP,
    "STATUS"           VARCHAR(50),
    "QTR_ID"           INTEGER,
    "MONTH_ID"         INTEGER,
    "YEAR_ID"          INTEGER,
    "PRODUCTLINE"      VARCHAR(100),
    "MSRP"             INTEGER,
    "PRODUCTCODE"      VARCHAR(50),
    "CUSTOMERNAME"     VARCHAR(200),
    "PHONE"            VARCHAR(50),
    "ADDRESSLINE1"     VARCHAR(200),
    "ADDRESSLINE2"     VARCHAR(200),
    "CITY"             VARCHAR(100),
    "STATE"            VARCHAR(100),
    "POSTALCODE"       VARCHAR(20),
    "COUNTRY"          VARCHAR(100),
    "TERRITORY"        VARCHAR(100),
    "CONTACTLASTNAME"  VARCHAR(100),
    "CONTACTFIRSTNAME" VARCHAR(100),
    "DEALSIZE"         VARCHAR(20)
);

-- ── Performance indexes ───────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sales_country    ON sales_data ("COUNTRY");
CREATE INDEX IF NOT EXISTS idx_sales_orderdate  ON sales_data ("ORDERDATE");
CREATE INDEX IF NOT EXISTS idx_sales_productline ON sales_data ("PRODUCTLINE");
CREATE INDEX IF NOT EXISTS idx_sales_year       ON sales_data ("YEAR_ID");
CREATE INDEX IF NOT EXISTS idx_sales_customer   ON sales_data ("CUSTOMERNAME");

-- ── Sample fixture data ───────────────────────────────────────────────
INSERT INTO sales_data VALUES
(10107,30,95.70, 2,2871.00, '2003-02-24','Shipped',  1,2,2003,'Motorcycles',      95, 'S10_1678','Land of Toys Inc.',       '2125557818','897 Long Airport Avenue',     NULL,'NYC',      'NY',   '10022',  'USA',       'NA','Yu',       'Kwai'),
(10121,34,81.35, 5,2765.90, '2003-05-07','Shipped',  2,5,2003,'Motorcycles',      95, 'S10_1678','Reims Collectables',      '26.47.1555','59 rue de lAbbaye',           NULL,'Reims',    NULL,  '51100',  'France',    'EMEA','Henriot','Paul'),
(10134,41,94.74, 2,3884.34, '2003-07-01','Shipped',  3,7,2003,'Motorcycles',      95, 'S10_1678','Lyon Souveniers',         '+33 1 46 62 7555','27 rue du Colonel Pierre Avia',NULL,'Paris', NULL,'75508','France','EMEA','Da Cunha','Daniel'),
(10145,45,83.26, 6,3746.70, '2003-08-25','Shipped',  3,8,2003,'Motorcycles',      95, 'S10_1678','Toys4GrownUps.com',       '6175559555','78934 Hillside Dr.',          NULL,'Pasadena','CA',  '90003',  'USA',       'NA','Young',    'Julie'),
(10159,49,100.00,14,5205.27,'2003-10-10','Shipped',  4,10,2003,'Motorcycles',     95, 'S10_1678','Corporate Gift Ideas Co.','6505551386','7734 Strong St.',             NULL,'San Francisco','CA','','USA','NA','Brown','Julie'),
(10168,36,96.66, 1,3479.76, '2003-10-28','Shipped',  4,10,2003,'Motorcycles',     95, 'S10_1678','Technics Stores Inc.',    '6505556809','9408 Furth Circle',           NULL,'Burlingame','CA','94217','USA','NA','Hirano','Juri'),
(10180,29,86.13, 2,2497.77, '2003-11-11','Shipped',  4,11,2003,'Motorcycles',     95, 'S10_1678','Daedalus Designs Imports','20.16.1555','184, chaussee de Tournai',    NULL,'Lille',    NULL,  '59000',  'France',    'EMEA','Rance',    'Martine'),
(10188,48,100.00,1,5512.32, '2003-11-18','Shipped',  4,11,2003,'Motorcycles',     95, 'S10_1678','Herkku Gifts',            '+47 2267 3215','Drammen 121020',             NULL,'Bergen',   NULL,  'N 5804','Norway',    'EMEA','Oeztan',   'Veysel'),
(10201,22,98.57, 2,2168.54, '2003-12-01','Shipped',  4,12,2003,'Motorcycles',     95, 'S10_1678','Mini Wheels Co.',         '6505555787','5557 North Pendale Street',   NULL,'San Francisco','CA','','USA','NA','Murphy','Julie'),
(10211,41,100.00,14,4708.44,'2004-01-15','Shipped',  1,1,2004,'Motorcycles',      95, 'S10_1678','Auto Canal Petit',        '(1) 47.55.6555','25, rue Lauriston',        NULL,'Paris',    NULL,  '75016',  'France',    'EMEA','Perrier', 'Dominique');

-- ── Helpful views ─────────────────────────────────────────────────────
CREATE OR REPLACE VIEW sales_by_country AS
    SELECT "COUNTRY",
           SUM("SALES")          AS total_sales,
           COUNT(*)              AS order_count,
           AVG("SALES")          AS avg_sale
    FROM   sales_data
    GROUP  BY "COUNTRY"
    ORDER  BY total_sales DESC;

CREATE OR REPLACE VIEW monthly_revenue AS
    SELECT "YEAR_ID",
           "MONTH_ID",
           SUM("SALES")  AS revenue,
           COUNT(*)      AS orders
    FROM   sales_data
    GROUP  BY "YEAR_ID", "MONTH_ID"
    ORDER  BY "YEAR_ID", "MONTH_ID";