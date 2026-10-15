# Sources

Every figure in the video comes from one of these. Accessed 2026-10-14T18:11:43Z.

## World Bank - World Development Indicators

- Indicator: `NY.GDP.PCAP.CD`
- URL: https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.CD?format=json&date=2021:2025&per_page=1000&mrnev=2
- Data year used: 2025
- World Bank last updated: 2026-10-08
- Accessed: 2026-10-14T18:11:43Z
- Covers 18 focus economies.

## World Bank - World Development Indicators

- Indicator: `NY.GDP.PCAP.PP.CD`
- URL: https://api.worldbank.org/v2/country/all/indicator/NY.GDP.PCAP.PP.CD?format=json&date=2021:2025&per_page=1000&mrnev=2
- Data year used: 2025
- World Bank last updated: 2026-10-08
- Accessed: 2026-10-14T18:11:43Z
- Covers 18 focus economies.

## Derived values

The price-level ratio is not fetched. It is computed in code as
`nominal GDP per capita / PPP GDP per capita` from the two series above,
and asserted before it is written to `facts.json`.

| Country | Nominal $/person | PPP $/person | Ratio | Year |
|---|---|---|---|---|
| United States | 90,027 | 90,027 | 1.000 | 2025 |
| United Kingdom | 57,602 | 64,606 | 0.892 | 2025 |
| Germany | 60,496 | 75,407 | 0.802 | 2025 |
| France | 48,986 | 63,975 | 0.766 | 2025 |
| Japan | 35,951 | 55,422 | 0.649 | 2025 |
| Korea, Rep. | 36,227 | 63,125 | 0.574 | 2025 |
| Mexico | 13,889 | 25,868 | 0.537 | 2025 |
| China | 13,862 | 29,333 | 0.473 | 2025 |
| Saudi Arabia | 34,537 | 73,784 | 0.468 | 2025 |
| Argentina | 14,898 | 32,587 | 0.457 | 2025 |
| Brazil | 10,713 | 23,433 | 0.457 | 2025 |
| South Africa | 6,598 | 15,906 | 0.415 | 2025 |
| Turkiye | 18,599 | 45,288 | 0.411 | 2025 |
| Russian Federation | 17,547 | 49,568 | 0.354 | 2025 |
| Indonesia | 5,060 | 17,660 | 0.286 | 2025 |
| India | 2,702 | 11,748 | 0.230 | 2025 |
| Egypt, Arab Rep. | 3,086 | 20,204 | 0.153 | 2025 |
| Nigeria | 1,224 | 9,532 | 0.128 | 2025 |

## Illustrative values

Any figure on screen marked EXAMPLE or ILLUSTRATION is not from this table.
It is a computed example written into `facts.json` with `kind: illustrative`.

