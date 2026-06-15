# Thailand Sources

Initial monitoring pool for Thailand Lead Radar.

## Core Thailand sources

| Source | Category | Filter | Notes |
| --- | --- | --- | --- |
| https://t.me/phuket_f | realty | min_score 0.62; intents realty, investment, expat_life | Core Phuket/realty source. Higher priority. Review delay: 3-18 min. |
| https://t.me/ru_chat_thailand | expat_life | min_score 0.68; intents relocation, realty, visa, expat_life, tourism | Broad Russian-speaking Thailand chat/source. Expect mixed quality. Review delay: 4-22 min. |
| https://t.me/thailand_russia_ru | relocation | min_score 0.68; intents relocation, realty, visa, expat_life, tourism | Thailand/Russia audience, useful for relocation and local questions. Review delay: 4-22 min. |

## Business and money sources

| Source | Category | Filter | Notes |
| --- | --- | --- | --- |
| https://t.me/dengivezde | finance | min_score 0.78; intents investment, business, finance | Monitor with stricter relevance threshold. Review delay: 10-40 min. |
| https://t.me/delaumoney | business | min_score 0.80; intents investment, business, finance | Monitor with stricter relevance threshold. Review delay: 10-40 min. |
| https://t.me/TrueBusines | business | min_score 0.80; intents investment, business, finance | Monitor with stricter relevance threshold. Review delay: 10-40 min. |
| https://t.me/nowtrendbrand | business | min_score 0.80; intents investment, business, finance | Monitor with stricter relevance threshold. Review delay: 10-40 min. |
| https://t.me/BusinesAdvisor | business | min_score 0.80; intents investment, business, finance | Monitor with stricter relevance threshold. Review delay: 10-40 min. |

## Recommended start settings

```env
PARSER_ENABLED=true
PARSER_INTERVAL_MINUTES=10
PARSER_LIMIT_PER_CHANNEL=20
RELEVANCE_THRESHOLD=0.70
```

The parser uses randomized reviewer delivery delays per channel. Claude also varies the draft style so comments do not look templated. All outbound decisions remain manual: the reviewer decides whether to send, save, skip or mark the item.

For the first 2-3 days, keep reviewer-first mode and watch `/daily_report` and `/channel_stats`.

## Channel filter commands

```text
/set_channel_min_score <channel_id> <0.00-1.00|->
/set_channel_intents <channel_id> <intent1,intent2|->
/set_channel_blocklist <channel_id> <word1,word2|->
```

Use `-` to reset a filter.

## Seed command

```bash
docker compose run --rm bot python -m scripts.seed_thailand_channels
```
