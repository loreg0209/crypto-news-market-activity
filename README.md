# News, Price Volatility and Market Activity in Major Cryptocurrencies

End-to-end **Data Management project** integrating hourly cryptocurrency market data from **Binance** with news indicators from **GDELT** to study short-term lead-lag relationships between news coverage, price movements and trading activity.

The project was developed for the **Data Management** course of the Master's Degree in Data Science at the **University of Milano-Bicocca**.

The analysis covers five major cryptocurrencies:

- Bitcoin (BTC)
- Ethereum (ETH)
- Binance Coin (BNB)
- Solana (SOL)
- Ripple (XRP)

Data are observed at **hourly frequency** over a two-year period from **January 25, 2024 to January 24, 2026**.

---

## Research Questions

The project investigates four main questions:

### RQ1 — News spikes and subsequent price movement

Do hours with unusually high news coverage coincide with larger price movements over the following **1h, 6h and 24h**?

### RQ2 — Price movement preceding news spikes

Are news spikes preceded by higher price volatility during the previous **1h, 6h and 24h**?

### RQ3 — News spikes and subsequent market activity

Do news spikes correspond to increased trading activity, measured through the number of trades, over the following **1h, 6h and 24h**?

### RQ4 — Price spikes and subsequent news coverage

Do extreme price movements increase future news volume and the probability of observing at least one news spike within the following 24 hours?

---

## Data Sources

### Binance

Hourly market data were collected through the **Binance Spot REST API** using 1-hour klines.

Main variables include:

- trading pair
- open and close timestamps
- open price
- high price
- low price
- close price
- volume
- number of trades

### GDELT

Hourly news indicators were collected through the **GDELT DOC 2.0 Timeline API** using cryptocurrency-specific keyword queries.

Main variables include:

- asset
- hourly timestamp
- hourly news count
- average tone
- share of news coverage

---

## Data Pipeline

The project implements an end-to-end data management workflow:

1. **GDELT data acquisition**  
   Download hourly cryptocurrency-related news indicators.

2. **Binance data acquisition**  
   Download hourly market data for the five selected cryptocurrencies.

3. **Pre-integration data quality checks**  
   Verify duplicates, completeness, hourly coverage and consistency.

4. **Data integration**  
   Standardize timestamps to UTC and align Binance and GDELT data on a common hourly timeline.

5. **Missing-data management**  
   Distinguish genuine zero-news observations from missing GDELT API buckets.

6. **Feature engineering**  
   Generate market-return, volatility and news-spike indicators.

7. **Relational storage**  
   Store the final enriched dataset in a relational database.

8. **SQL analysis**  
   Execute the four research questions using SQL window functions and lead/lag horizons.

---

## Data Quality

Before integration, both sources were evaluated in terms of:

- uniqueness
- completeness
- hourly coverage
- duplicate observations
- price consistency
- trading-volume consistency
- missing news observations
- sentiment quality

Binance provides complete hourly coverage across the selected period, while GDELT contains some missing hourly buckets.

These missing GDELT observations are explicitly tracked rather than automatically interpreted as genuine zero-news hours.

---

## Data Integration

All timestamps are standardized to **UTC** and rounded to hourly buckets.

A complete hourly reference timeline is generated for each cryptocurrency and used as the base for integrating the two data sources.

A dedicated variable:

```text
gdelt_missing
```

is used to distinguish between:

- actual hours with no detected news
- hours missing because of the GDELT endpoint

This preserves information about data availability during downstream analyses.

---

## Feature Engineering

### Market Features

Hourly price movement is represented through continuously compounded returns:

```text
ret_1h = log(close_t / close_t-1)
```

An intrahour volatility indicator is also derived from the high-low price range.

### News Features

A binary `news_spike` variable identifies unusually high news activity.

A news spike occurs when hourly news volume exceeds an asset-specific **95th percentile threshold**, calculated separately by semester.

Using semester-specific thresholds allows the definition of unusual media attention to adapt to changes in overall news intensity over time.

The final enriched dataset contains **87,600 rows and 16 columns**.

---

## Data Storage and SQL Analysis

The final enriched dataset is stored in a relational database.

The main table uses the composite primary key:

```text
(asset, ts_hour_utc)
```

This guarantees one observation for each asset-hour combination and prevents duplicates.

The four research questions are evaluated directly in SQL using **window functions**.

Lead and lag windows of:

- 1 hour
- 6 hours
- 24 hours

are used to compare market and news behaviour before and after specific events.

---

## Main Results

### RQ1 — News Spikes and Subsequent Price Movement

Across all five cryptocurrencies, news-spike hours are followed by higher average absolute price movement.

The strongest relative effects occur at the **1-hour horizon**:

- BTC: +24.2%
- XRP: +25.5%
- ETH: +20.3%
- SOL: +17.3%
- BNB: +9.3%

The effect remains positive at 6h and 24h but generally weakens over time.

### RQ2 — Price Movement Before News Spikes

News spikes generally occur during periods of already elevated price movement.

The strongest pre-spike build-up appears for XRP and SOL over longer lookback windows, while BTC shows a clear gap already at the 1-hour horizon.

ETH shows comparatively weaker pre-spike dynamics.

### RQ3 — News Spikes and Market Activity

News-spike hours are followed by higher trading activity at short horizons for all five assets.

The largest 1-hour uplifts are approximately:

- SOL: +38%
- XRP: +37%
- BNB: +35%
- BTC: +27%

The effect remains visible at longer horizons for most assets, while ETH becomes the main exception over 24 hours.

### RQ4 — Price Spikes and Subsequent News Coverage

Extreme price movements are generally followed by higher subsequent news coverage and a higher probability of observing at least one news spike within 24 hours.

The clearest pattern is observed for BTC, XRP, SOL and BNB.

ETH is the main exception, showing weaker or negative effects on future news volume at longer horizons.

---

## Conclusions

The analysis suggests a **bidirectional short-term relationship between cryptocurrency markets and news activity**.

News spikes tend to be associated with:

- stronger subsequent price movements
- increased trading activity

At the same time:

- elevated price movement often precedes news spikes
- extreme price movements can increase subsequent media attention

The strongest relationships generally occur within the first **1–6 hours** and tend to weaken over the 24-hour horizon.

The analysis is descriptive and does not claim causal relationships.

---

## Project Files

### `code/`

- `api gdelt.ipynb` — GDELT news data acquisition
- `binance_klines.py` — Binance market data acquisition
- `enrichment 2y.ipynb` — data integration, missingness management and feature engineering
- `data storage 2y.ipynb` — relational storage and SQL analyses for RQ1–RQ4

---

## Documentation

[View the full project report](docs/DM_project%20-%20Lorenzo%20Luciano%20Gulizia%20mat.882806.pdf)

[View the project presentation](docs/crypto_news_project_presentation.pdf)

---

## Author

**Lorenzo Gulizia**

Master's Degree in Data Science  
University of Milano-Bicocca  
Academic Year 2025/2026
