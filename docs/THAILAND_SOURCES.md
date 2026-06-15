# Thailand Sources

Initial monitoring pool for Thailand Lead Radar.

## Core Thailand sources

| Source | Category | Notes |
| --- | --- | --- |
| https://t.me/phuket_f | realty | Core Phuket/realty source. Higher priority. Review delay: 3-18 min. |
| https://t.me/ru_chat_thailand | expat_life | Broad Russian-speaking Thailand chat/source. Expect mixed quality. Review delay: 4-22 min. |
| https://t.me/thailand_russia_ru | relocation | Thailand/Russia audience, useful for relocation and local questions. Review delay: 4-22 min. |

## Business and money sources

| Source | Category | Notes |
| --- | --- | --- |
| https://t.me/dengivezde | finance | Monitor with stricter relevance threshold. Review delay: 10-40 min. |
| https://t.me/delaumoney | business | Monitor with stricter relevance threshold. Review delay: 10-40 min. |
| https://t.me/TrueBusines | business | Monitor with stricter relevance threshold. Review delay: 10-40 min. |
| https://t.me/nowtrendbrand | business | Monitor with stricter relevance threshold. Review delay: 10-40 min. |
| https://t.me/BusinesAdvisor | business | Monitor with stricter relevance threshold. Review delay: 10-40 min. |

## Recommended start settings

```env
PARSER_ENABLED=true
PARSER_INTERVAL_MINUTES=10
PARSER_LIMIT_PER_CHANNEL=20
RELEVANCE_THRESHOLD=0.70
```

The parser uses randomized reviewer delivery delays per channel. Claude also varies the draft style so comments do not look templated. All outbound decisions remain manual: the reviewer decides whether to send, save, skip or mark the item.

For the first 2-3 days, keep reviewer-first mode and watch `/daily_report` and `/channel_stats`.

## Seed command

```bash
docker compose run --rm bot python -m scripts.seed_thailand_channels
```
