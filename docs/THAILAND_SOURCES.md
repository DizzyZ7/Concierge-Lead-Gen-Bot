# Thailand Sources

Initial monitoring pool for Thailand Lead Radar.

## Core Thailand sources

| Source | Category | Notes |
| --- | --- | --- |
| https://t.me/phuket_f | realty | Core Phuket/realty source. Higher priority. |
| https://t.me/ru_chat_thailand | expat_life | Broad Russian-speaking Thailand chat/source. Expect mixed quality. |
| https://t.me/thailand_russia_ru | relocation | Thailand/Russia audience, useful for relocation and local questions. |

## Business and money sources

| Source | Category | Notes |
| --- | --- | --- |
| https://t.me/dengivezde | finance | Monitor with stricter relevance threshold. |
| https://t.me/delaumoney | business | Monitor with stricter relevance threshold. |
| https://t.me/TrueBusines | business | Monitor with stricter relevance threshold. |
| https://t.me/nowtrendbrand | business | Monitor with stricter relevance threshold. |
| https://t.me/BusinesAdvisor | business | Monitor with stricter relevance threshold. |

## Recommended start settings

```env
PARSER_ENABLED=true
PARSER_INTERVAL_MINUTES=10
PARSER_LIMIT_PER_CHANNEL=20
RELEVANCE_THRESHOLD=0.70
```

For the first 2-3 days, keep reviewer-first mode and watch `/daily_report` and `/channel_stats`.

## Seed command

```bash
docker compose run --rm bot python -m scripts.seed_thailand_channels
```
