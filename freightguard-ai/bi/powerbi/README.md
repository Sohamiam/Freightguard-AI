# Power BI setup
1. Get Data > PostgreSQL: server `localhost:5432`, database `freightguard`, user/password `fg`. Load `mv_invoice_facts`, `mv_carrier_recovery`, `mv_typology_monthly`, `v_dispute_outcomes` (Import mode; schedule refresh after `REFRESH MATERIALIZED VIEW CONCURRENTLY`).
2. Create a `Date` table (`CALENDAR`) and mark it as the date table.
3. Relationships (star schema): `Date[Date]` 1:* `mv_invoice_facts[invoice_date]`; `mv_invoice_facts[carrier]` * : 1 `mv_carrier_recovery[carrier]` (single direction).
4. Paste measures from `measures.dax`.
5. Pages: Executive (cards: Total Billed, Identified Overcharge, Savings % of Spend; line: Overcharge MoM), Carriers (bar: overcharge by carrier), Typologies (stacked column by month), Ops (Flag Precision, Approval Rate %).
Note: `.pbix` binaries are not generated here; build the report from this spec in Power BI Desktop.
