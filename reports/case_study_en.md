# Case study: Argentina retail pulse

## Executive summary

In May 2026 nominal sales increased `25.9%` year over year in supermarkets and `23.7%` in
wholesale self-service stores, while original real indices fell `0.7%` and `2.3%`. The
seasonally adjusted monthly signal was positive (`0.9%` and `2.3%`), but both real indices
remained close to `80.5` on their own 2017=100 bases.

Mix also shifted. Credit led supermarkets at `45.0%`, with cash at `16.5%`. Other payment
methods led wholesale at `32.3%`. Grocery accounted for `27.1%` of supermarket nominal mix
and `44.4%` of wholesale mix. Supermarket online share was `3.43%`; wholesale channel
detail has not been observed after August 2022.

## Objectives

- Separate current-price billing from real performance.
- Describe payment, category and channel shifts within each format.
- Expose coverage, units and quality before results support decisions.

## Methodology

The workflow processes two official monthly series from January 2017 through May 2026. It
validates contracts, continuity, non-negative values and reconciliations. Detailed sales
are current-price thousand ARS; headline nominal and constant sales are million ARS; real
indices use 2017=100. The formats cover separate survey populations and are never added.
May 2026 belongs to a partial year.

## Findings

| May 2026 metric | Supermarkets | Wholesale |
|---|---:|---:|
| Nominal sales, million ARS | `2,502,789.7` | `388,237.1` |
| Nominal YoY change | `25.9%` | `23.7%` |
| Original real index | `80.5` | `80.6` |
| Real YoY change | `-0.7%` | `-2.3%` |
| Seasonally adjusted MoM change | `0.9%` | `2.3%` |

The largest supermarket payment shift was other methods (`+3.17 pp`), while debit lost
`2.72 pp`. Wholesale cash gained `2.92 pp` and debit lost `4.44 pp`. These are descriptive
composition changes, not causal evidence.

The top supermarket categories were grocery (`27.1%`), meat (`14.6%`), cleaning and
personal care (`13.1%`), dairy (`11.3%`) and beverages (`9.1%`). Grocery (`44.4%`) and
cleaning/personal care (`25.9%`) led wholesale. These nominal shares can reflect relative
prices as well as quantities.

## KPIs and quality

The dashboard keeps the real index, real YoY, seasonally adjusted MoM, nominal sales,
shares, percentage points and effective dates separate. All `11` `HIGH` checks passed.
That gate confirms implemented rules; it does not prove that the source is perfect or complete.

## Recommendations

- Manage each format separately and use real indices for recovery targets.
- Investigate the rise in other payment methods without assigning an unobserved cause.
- Add margin, unit and price evidence before turning nominal mix into assortment actions.
- Display channel effective dates and never replace unavailable wholesale months with zero.

## Risks

- 2026 is partial and trend-cycle endpoints can be revised.
- The source does not provide units, margin, baskets, customers or promotional causality.
- The two formats do not form one combined market-share denominator.
- Wholesale channel data after August 2022 is structurally unavailable.

## Next steps

Deploy and load SQL Server, refresh the PBIP, reconcile visible KPIs to the CSVs, and
certify desktop/mobile rendering in Power BI Desktop before publication.
