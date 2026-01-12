# 🔮 Oracle Betting System

> **AI-powered system that finds where bookmakers contradict themselves — and turns their mistakes into your edge.**

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Sports](https://img.shields.io/badge/Sports-Football%20%7C%20Basketball-orange.svg)

---

## 🧠 The Philosophy

Most bettors ask: *"Who will win?"*

The Oracle asks: *"Where did the bookmaker make a mistake?"*

**Here's the secret:** Bookmakers price 100+ markets per match. Each market is priced by different traders. Sometimes these markets **contradict each other**.

When Market A says **45%** and Market B says **52%** for the same outcome — someone is wrong.

**The Oracle finds these contradictions, calculates true probabilities, and shows you where the VALUE is.**

---

## 🎯 How It Works
```
┌─────────────────────────────────────────────────────────────────┐
│  BOOKMAKER MARKETS (100+ per match)                             │
│  ├── 1X2 (Home/Draw/Away)                                       │
│  ├── Double Chance                                              │
│  ├── Over/Under                                                 │
│  ├── Both Teams To Score                                        │
│  ├── Asian Handicap                                             │
│  ├── Team Totals                                                │
│  └── ... and many more                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  🔮 ORACLE ANALYSIS                                             │
│  ├── Extract all market probabilities                           │
│  ├── Remove bookmaker margins                                   │
│  ├── Check mathematical relationships                           │
│  ├── Find contradictions                                        │
│  └── Calculate TRUE probabilities                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  💰 OUTPUT                                                      │
│  ├── Contradiction Report                                       │
│  ├── Win Probabilities                                          │
│  ├── Value Bet Analysis                                         │
│  └── 🎯 RECOMMENDED ACTION: BET or SKIP                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚽🏀 Supported Sports

| Sport | File | Markets Analyzed |
|-------|------|------------------|
| **Football/Soccer** | `football/market_oracle.py` | 1X2, Double Chance, O/U, BTTS, Asian Handicap, European Handicap, Draw No Bet, Teams to Score |
| **Basketball** | `basketball/basketball_oracle.py` | Moneyline, Point Spread, Game Total, Team Totals, Half Totals, Quarter Markets |

---

## 🚀 Quick Start

### Requirements
- Python 3.8+
- Windows (for .bat files) or run directly with Python

### Installation
```bash
git clone https://github.com/Princeeze744/Oracle-Betting-System.git
cd Oracle-Betting-System
```

### Run Football Oracle
```bash
cd football
python market_oracle.py
```

### Run Basketball Oracle
```bash
cd basketball
python basketball_oracle.py
```

### Usage
1. Copy **ALL markets** from your bookmaker (the more markets, the better)
2. Run the Oracle
3. Paste the data
4. Press Enter twice
5. Get your analysis and **RECOMMENDED ACTION**

---

## 📊 Sample Output
```
================================================================================
🔮 ORACLE PREDICTION
================================================================================
   Predicted Score: 1-1
   Probability: 13.61%
   
   Match Outcome Probabilities:
      Home Win: 43.83%
      Draw:     26.05%
      Away Win: 30.13%

================================================================================
💰 VALUE BET ANALYSIS
================================================================================
   HOME WIN:  Odds 2.05 (implied 48.8%) vs Oracle 43.8%
              Edge: -5.0% ❌ NO VALUE

   DRAW:      Odds 4.28 (implied 23.4%) vs Oracle 26.0%
              Edge: +2.7% ✅ VALUE

   AWAY WIN:  Odds 3.34 (implied 29.9%) vs Oracle 30.1%
              Edge: +0.2% ❌ NO VALUE

================================================================================
🎯 RECOMMENDED ACTION
================================================================================
   ⏭️ SKIP - No significant value found
================================================================================
```

---

## 🎯 Decision Guide

| Output | Meaning | Action |
|--------|---------|--------|
| 🎯 **BET** ... Prediction + Value ALIGN ✅ | Best case - Oracle prediction has positive edge | **Bet with confidence** |
| 💰 **VALUE BET** ... | Edge ≥5% on non-predicted outcome | **Small bet on value** |
| ⚠️ **SMALL VALUE** ... | Edge 3-5% | **Very small bet or skip** |
| ⏭️ **SKIP** | No value found | **Don't bet this match** |

---

## 🧮 Mathematical Contradictions Detected

### Football
- 1X2 vs Double Chance (must match mathematically)
- BTTS vs Teams to Score (same event, different market)
- Under 0.5 vs Teams to Score: None (both = 0-0)
- Draw No Bet vs Asian Handicap 0 (identical bets)
- Handicap chain consistency

### Basketball
- Team Totals vs Game Total (Home + Away = Total)
- Moneyline vs Point Spread alignment
- Half Totals vs Game Total
- Spread chain consistency
- Over/Under chain consistency

---

## 💡 The Edge

> *"Don't bet on who wins. Bet on where the bookmaker made a mistake."*

Traditional betting: Win rate matters
Oracle betting: **Value matters**

You can win 40% of bets and be **profitable** — if every bet has positive expected value.

---

## 📈 Results

The Oracle finds value in approximately **10-20%** of matches analyzed. This is by design:

- ❌ Skip 80% of matches (no edge)
- ✅ Bet 20% of matches (with edge)
- 💰 Long-term profit through mathematical advantage

---

## 🤝 For Tipsters & Partners

Interested in:
- White-labeling this system?
- API access?
- Collaboration opportunities?

**Contact:** [Your Email/Twitter/LinkedIn]

---

## ⚠️ Disclaimer

This tool is for educational and entertainment purposes. Gambling involves risk. Never bet more than you can afford to lose. Past performance does not guarantee future results.

---

## 📜 License

MIT License - Use freely, attribution appreciated.

---

## ⭐ Star This Repo

If the Oracle helps you find value, give it a ⭐ — it helps others discover it!

---

**Built with 🧠 by [Princeeze744](https://github.com/Princeeze744)**