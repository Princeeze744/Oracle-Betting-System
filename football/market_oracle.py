#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║         MARKET CONTRADICTION ANALYZER - THE ORACLE SYSTEM v1.0                ║
║                                                                               ║
║  Philosophy: The bookmaker prices many markets. Each market is a separate     ║
║  "witness" telling a story about the match. If all witnesses agree, they're   ║
║  consistent. If they DISAGREE, someone made a mistake - and mistakes = edges. ║
║                                                                               ║
║  This system finds contradictions WITHIN the bookmaker's own odds and uses    ║
║  pure mathematics to extract the "true" score probability that was hidden.    ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import re
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class MarketData:
    """Holds extracted market data"""
    name: str
    outcomes: Dict[str, float]  # outcome -> odds
    
    
@dataclass
class MarketProbabilities:
    """Holds fair probabilities for a market"""
    name: str
    probs: Dict[str, float]  # outcome -> probability
    margin: float  # overround percentage


@dataclass 
class Contradiction:
    """Represents a contradiction between markets"""
    market1: str
    market2: str
    description: str
    expected: float
    actual: float
    difference: float  # positive = opportunity
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"


class MarketContradictionAnalyzer:
    """
    Analyzes multiple betting markets to find internal contradictions.
    
    Mathematical Constraints That MUST Hold:
    
    1. 1X2 ↔ Double Chance:
       P(1) + P(X) = P(1X)
       P(X) + P(2) = P(X2)
       P(1) + P(2) = P(12)
    
    2. 1X2 ↔ Draw No Bet:
       P(DNB Home) = P(1) / (P(1) + P(2))
       P(DNB Away) = P(2) / (P(1) + P(2))
    
    3. Asian Handicap 0 = Draw No Bet
    
    4. Asian Handicap -0.5 Home = P(Home Win) = P(1)
    
    5. BTTS = Teams to Score: Both
    
    6. Teams to Score: None = P(0-0) = P(Under 0.5)
    
    7. European Handicap relationships
    """
    
    def __init__(self):
        self.markets: Dict[str, MarketData] = {}
        self.fair_probs: Dict[str, MarketProbabilities] = {}
        self.contradictions: List[Contradiction] = []
        self.home_team = ""
        self.away_team = ""
        
    def odds_to_prob(self, odds: float) -> float:
        """Convert decimal odds to implied probability"""
        if odds <= 0:
            return 0
        return 1 / odds
    
    def remove_margin(self, probs: Dict[str, float]) -> Dict[str, float]:
        """Remove bookmaker margin from probabilities"""
        total = sum(probs.values())
        if total == 0:
            return probs
        return {k: v / total for k, v in probs.items()}
    
    def calculate_margin(self, odds_dict: Dict[str, float]) -> float:
        """Calculate bookmaker margin (overround)"""
        total_prob = sum(1/odds for odds in odds_dict.values() if odds > 0)
        return (total_prob - 1) * 100  # As percentage
    
    def parse_raw_data(self, raw_data: str) -> None:
        """Parse raw bookmaker data and extract all markets"""
        lines = raw_data.strip().split('\n')
        
        # Extract team names from first line
        first_line = lines[0].strip()
        if ' vs ' in first_line or ' v ' in first_line:
            sep = ' vs ' if ' vs ' in first_line else ' v '
            parts = first_line.split(sep)
            if len(parts) >= 2:
                self.home_team = parts[0].strip()
                self.away_team = parts[1].split('\n')[0].strip()
        
        current_market = None
        market_outcomes = {}
        market_counter = {}  # Track how many of each market type we've seen
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Detect market headers
            if self._is_market_header(line):
                # Save previous market if exists
                if current_market and market_outcomes:
                    self.markets[current_market] = MarketData(
                        name=current_market,
                        outcomes=market_outcomes.copy()
                    )
                
                # Handle duplicate market names (e.g., multiple Over/Under)
                base_market = line
                if base_market in market_counter:
                    market_counter[base_market] += 1
                    # For Over/Under, we'll rename based on the first outcome we see
                    current_market = f"{base_market}_{market_counter[base_market]}"
                else:
                    market_counter[base_market] = 1
                    current_market = base_market
                
                market_outcomes = {}
                i += 1
                continue
            
            # Try to parse outcome with odds
            parsed = self._parse_outcome_line(line)
            if parsed and current_market:
                outcome, odds = parsed
                market_outcomes[outcome] = odds
                
                # If this is an Over/Under market with _N suffix, rename it properly
                if current_market.startswith("Over/Under_") and "Over" in outcome:
                    # Extract the line from the outcome (e.g., "Over 2.5" -> "2.5")
                    match = re.search(r'(\d+\.5)', outcome)
                    if match:
                        line_num = match.group(1)
                        # Rename to include the line
                        new_name = f"Over/Under {line_num}"
                        if new_name not in self.markets:
                            # Update the name (will be saved when we hit next market)
                            # Actually, let's just keep track and fix at the end
                            pass
            
            i += 1
        
        # Save last market
        if current_market and market_outcomes:
            self.markets[current_market] = MarketData(
                name=current_market,
                outcomes=market_outcomes.copy()
            )
        
        # Post-process: Rename Over/Under markets based on their content
        renamed_markets = {}
        for name, market in self.markets.items():
            if name.startswith("Over/Under"):
                # Find the line from the outcomes
                for outcome in market.outcomes.keys():
                    match = re.search(r'(\d+\.5)', outcome)
                    if match:
                        new_name = f"Over/Under {match.group(1)}"
                        renamed_markets[new_name] = market
                        break
                else:
                    renamed_markets[name] = market
            else:
                renamed_markets[name] = market
        
        self.markets = renamed_markets
        
        # Calculate fair probabilities for all markets
        self._calculate_fair_probs()
    
    def _is_market_header(self, line: str) -> bool:
        """Check if line is a market header"""
        market_headers = [
            '1X2', 'Over/Under', 'Double Chance', 'Handicap', 'Asian Handicap',
            'GG/NG', 'Draw No Bet', 'Teams to Score', 'Correct Score',
            'Odd/Even', 'Home No Bet', 'Away No Bet', 'Winning Margin',
            'Any Team', 'Home Team', 'Away Team', 'Goal Bounds'
        ]
        return any(header in line for header in market_headers)
    
    def _parse_outcome_line(self, line: str) -> Optional[Tuple[str, float]]:
        """Parse an outcome line and extract outcome name and odds"""
        
        # Special handling for Over/Under format: "Over X.5Y.YY" or "Under X.5Y.YY"
        # The line (0.5, 1.5, 2.5, etc.) is followed directly by the odds
        ou_match = re.match(r'^(Over|Under)\s*(\d+\.5)([\d.]+)$', line, re.IGNORECASE)
        if ou_match:
            action = ou_match.group(1)  # Over or Under
            line_num = ou_match.group(2)  # 0.5, 1.5, etc.
            odds_str = ou_match.group(3)  # The odds
            try:
                odds = float(odds_str)
                if 1.01 <= odds <= 500:
                    return (f"{action} {line_num}", odds)
            except ValueError:
                pass
        
        # Handle outcomes with parentheses like "Home (0:1)2.45"
        paren_match = re.match(r'^(.*?\([^)]+\))([\d]+\.[\d]+)$', line)
        if paren_match:
            outcome = paren_match.group(1).strip()
            try:
                odds = float(paren_match.group(2))
                if 1.01 <= odds <= 500:
                    return (outcome, odds)
            except ValueError:
                pass
        
        # General pattern: any text followed by a decimal number at the end
        # Use greedy match for text, then capture the last decimal number
        general_match = re.match(r'^(.+?)([\d]+\.[\d]+)$', line)
        if general_match:
            outcome = general_match.group(1).strip()
            try:
                odds = float(general_match.group(2))
                if 1.01 <= odds <= 500:
                    return (outcome, odds)
            except ValueError:
                pass
        
        return None
    
    def _calculate_fair_probs(self) -> None:
        """Calculate fair (margin-removed) probabilities for all markets"""
        for name, market in self.markets.items():
            raw_probs = {k: self.odds_to_prob(v) for k, v in market.outcomes.items()}
            
            # Double Chance is NOT a mutually exclusive market
            # Each option has its own margin, so we need a different approach
            if 'Double Chance' in name:
                # For Double Chance, we estimate margin from 1X2 and apply that
                # Or we can use the raw implied probability from odds
                # The "fair" probability for DC 1X should match P(1) + P(X) from 1X2
                # For now, just use the raw probabilities (let the contradiction checker compare)
                fair_probs = raw_probs
                margin = sum(raw_probs.values()) - 1  # This will be high but that's expected
            else:
                fair_probs = self.remove_margin(raw_probs)
                margin = self.calculate_margin(market.outcomes)
            
            self.fair_probs[name] = MarketProbabilities(
                name=name,
                probs=fair_probs,
                margin=margin
            )
    
    def get_1x2_probs(self) -> Optional[Dict[str, float]]:
        """Get 1X2 probabilities"""
        for name, mp in self.fair_probs.items():
            if name == '1X2' or (name.startswith('1X2') and '1UP' not in name and '2UP' not in name):
                return mp.probs
        return None
    
    def get_double_chance_probs(self) -> Optional[Dict[str, float]]:
        """Get Double Chance probabilities"""
        for name, mp in self.fair_probs.items():
            if 'Double Chance' in name:
                return mp.probs
        return None
    
    def get_dnb_probs(self) -> Optional[Dict[str, float]]:
        """Get Draw No Bet probabilities"""
        for name, mp in self.fair_probs.items():
            if 'Draw No Bet' in name:
                return mp.probs
        return None
    
    def get_ah0_probs(self) -> Optional[Dict[str, float]]:
        """Get Asian Handicap 0 probabilities"""
        for name, mp in self.fair_probs.items():
            if 'Asian Handicap 0' in name or 'Asian Handicap -0' in name:
                if '-0.5' not in name:  # Exclude AH -0.5
                    return mp.probs
        return None
    
    def get_btts_probs(self) -> Optional[Dict[str, float]]:
        """Get BTTS (GG/NG) probabilities"""
        for name, mp in self.fair_probs.items():
            if 'GG/NG' in name and '2+' not in name:
                return mp.probs
        return None
    
    def get_teams_to_score_probs(self) -> Optional[Dict[str, float]]:
        """Get Teams to Score probabilities"""
        for name, mp in self.fair_probs.items():
            if 'Teams to Score' in name:
                return mp.probs
        return None
    
    def get_over_under_probs(self, line: float) -> Optional[Dict[str, float]]:
        """Get Over/Under probabilities for a specific line"""
        target = f"Over/Under"
        for name, mp in self.fair_probs.items():
            if target in name:
                # Check if this market has the right line
                for outcome in mp.probs.keys():
                    if str(line) in outcome:
                        return mp.probs
        return None
    
    def analyze_contradictions(self) -> List[Contradiction]:
        """Main analysis - find all market contradictions"""
        self.contradictions = []
        
        # Get base probabilities
        p1x2 = self.get_1x2_probs()
        pdc = self.get_double_chance_probs()
        pdnb = self.get_dnb_probs()
        pah0 = self.get_ah0_probs()
        pbtts = self.get_btts_probs()
        ptts = self.get_teams_to_score_probs()
        
        # === CONTRADICTION CHECK 1: 1X2 vs Double Chance ===
        if p1x2 and pdc:
            self._check_1x2_vs_double_chance(p1x2, pdc)
        
        # === CONTRADICTION CHECK 2: 1X2 vs Draw No Bet ===
        if p1x2 and pdnb:
            self._check_1x2_vs_dnb(p1x2, pdnb)
        
        # === CONTRADICTION CHECK 3: Draw No Bet vs Asian Handicap 0 ===
        if pdnb and pah0:
            self._check_dnb_vs_ah0(pdnb, pah0)
        
        # === CONTRADICTION CHECK 4: BTTS vs Teams to Score ===
        if pbtts and ptts:
            self._check_btts_vs_teams_to_score(pbtts, ptts)
        
        # === CONTRADICTION CHECK 5: Teams to Score consistency ===
        if ptts:
            self._check_teams_to_score_consistency(ptts)
        
        # === CONTRADICTION CHECK 6: Over/Under vs Teams to Score ===
        if ptts:
            self._check_ou_vs_teams_to_score(ptts)
        
        # === CONTRADICTION CHECK 7: Asian Handicap Chain ===
        self._check_asian_handicap_chain()
        
        # === CONTRADICTION CHECK 8: European Handicap vs 1X2 ===
        if p1x2:
            self._check_european_handicap_vs_1x2(p1x2)
        
        return self.contradictions
    
    def _check_1x2_vs_double_chance(self, p1x2: Dict, pdc: Dict) -> None:
        """Check if 1X2 and Double Chance agree"""
        # Get fair (margin-removed) 1X2 probabilities
        p_home = self._get_prob(p1x2, ['Home', '1', 'home'])
        p_draw = self._get_prob(p1x2, ['Draw', 'X', 'draw'])
        p_away = self._get_prob(p1x2, ['Away', '2', 'away'])
        
        # For Double Chance, we use raw implied probability from odds
        # Then we need to estimate the margin to get fair probability
        # DC odds already have ~5-10% margin, so we remove approximately that
        dc_margin_estimate = 0.06  # Assume 6% margin on DC
        
        p_1x_raw = self._get_prob(pdc, ['Home or Draw', '1X', '1x'])
        p_x2_raw = self._get_prob(pdc, ['Draw or Away', 'X2', 'x2'])
        p_12_raw = self._get_prob(pdc, ['Home or Away', '12'])
        
        # Remove estimated margin from DC probabilities
        # Fair prob ≈ raw_prob / (1 + margin)
        if p_1x_raw:
            p_1x = p_1x_raw / (1 + dc_margin_estimate)
        else:
            p_1x = None
            
        if p_x2_raw:
            p_x2 = p_x2_raw / (1 + dc_margin_estimate)
        else:
            p_x2 = None
            
        if p_12_raw:
            p_12 = p_12_raw / (1 + dc_margin_estimate)
        else:
            p_12 = None
        
        # Check 1X = Home + Draw
        if p_home and p_draw and p_1x:
            expected = p_home + p_draw
            diff = abs(expected - p_1x)
            if diff > 0.03:  # More than 3% difference
                # Determine which way the disagreement goes
                if p_1x > expected:
                    direction = f"DC overestimates 1X by {diff:.1%}"
                else:
                    direction = f"DC underestimates 1X by {diff:.1%}"
                
                self.contradictions.append(Contradiction(
                    market1="1X2",
                    market2="Double Chance 1X",
                    description=f"1X2 implies P(1X)={expected:.1%}, DC implies {p_1x:.1%}. {direction}",
                    expected=expected,
                    actual=p_1x,
                    difference=diff,
                    severity=self._get_severity(diff)
                ))
        
        # Check X2 = Draw + Away
        if p_draw and p_away and p_x2:
            expected = p_draw + p_away
            diff = abs(expected - p_x2)
            if diff > 0.03:
                if p_x2 > expected:
                    direction = f"DC overestimates X2 by {diff:.1%}"
                else:
                    direction = f"DC underestimates X2 by {diff:.1%}"
                    
                self.contradictions.append(Contradiction(
                    market1="1X2",
                    market2="Double Chance X2",
                    description=f"1X2 implies P(X2)={expected:.1%}, DC implies {p_x2:.1%}. {direction}",
                    expected=expected,
                    actual=p_x2,
                    difference=diff,
                    severity=self._get_severity(diff)
                ))
        
        # Check 12 = Home + Away
        if p_home and p_away and p_12:
            expected = p_home + p_away
            diff = abs(expected - p_12)
            if diff > 0.03:
                if p_12 > expected:
                    direction = f"DC overestimates 12 by {diff:.1%}"
                else:
                    direction = f"DC underestimates 12 by {diff:.1%}"
                    
                self.contradictions.append(Contradiction(
                    market1="1X2",
                    market2="Double Chance 12",
                    description=f"1X2 implies P(12)={expected:.1%}, DC implies {p_12:.1%}. {direction}",
                    expected=expected,
                    actual=p_12,
                    difference=diff,
                    severity=self._get_severity(diff)
                ))
    
    def _check_1x2_vs_dnb(self, p1x2: Dict, pdnb: Dict) -> None:
        """Check if 1X2 and Draw No Bet agree"""
        p_home = self._get_prob(p1x2, ['Home', '1'])
        p_away = self._get_prob(p1x2, ['Away', '2'])
        
        p_dnb_home = self._get_prob(pdnb, ['Home'])
        p_dnb_away = self._get_prob(pdnb, ['Away'])
        
        if p_home and p_away and p_dnb_home:
            # DNB Home should equal P(Home) / (P(Home) + P(Away))
            expected = p_home / (p_home + p_away) if (p_home + p_away) > 0 else 0
            diff = abs(expected - p_dnb_home)
            if diff > 0.02:
                self.contradictions.append(Contradiction(
                    market1="1X2",
                    market2="Draw No Bet",
                    description=f"1X2 implies DNB Home={expected:.2%}, but DNB shows {p_dnb_home:.2%}",
                    expected=expected,
                    actual=p_dnb_home,
                    difference=diff,
                    severity=self._get_severity(diff)
                ))
    
    def _check_dnb_vs_ah0(self, pdnb: Dict, pah0: Dict) -> None:
        """Check if Draw No Bet equals Asian Handicap 0"""
        p_dnb_home = self._get_prob(pdnb, ['Home'])
        p_dnb_away = self._get_prob(pdnb, ['Away'])
        
        p_ah0_home = self._get_prob(pah0, ['Home', 'Home (0)'])
        p_ah0_away = self._get_prob(pah0, ['Away', 'Away (0)'])
        
        if p_dnb_home and p_ah0_home:
            diff = abs(p_dnb_home - p_ah0_home)
            if diff > 0.02:
                self.contradictions.append(Contradiction(
                    market1="Draw No Bet",
                    market2="Asian Handicap 0",
                    description=f"DNB Home={p_dnb_home:.2%}, but AH0 Home={p_ah0_home:.2%} (should be EQUAL)",
                    expected=p_dnb_home,
                    actual=p_ah0_home,
                    difference=diff,
                    severity=self._get_severity(diff)
                ))
    
    def _check_btts_vs_teams_to_score(self, pbtts: Dict, ptts: Dict) -> None:
        """Check if BTTS equals Teams to Score: Both"""
        p_btts_yes = self._get_prob(pbtts, ['Yes'])
        p_tts_both = self._get_prob(ptts, ['Both teams', 'Both'])
        
        if p_btts_yes and p_tts_both:
            diff = abs(p_btts_yes - p_tts_both)
            if diff > 0.02:
                self.contradictions.append(Contradiction(
                    market1="GG/NG (BTTS)",
                    market2="Teams to Score",
                    description=f"BTTS Yes={p_btts_yes:.2%}, but Teams to Score: Both={p_tts_both:.2%} (should be EQUAL)",
                    expected=p_btts_yes,
                    actual=p_tts_both,
                    difference=diff,
                    severity=self._get_severity(diff)
                ))
    
    def _check_teams_to_score_consistency(self, ptts: Dict) -> None:
        """Check if Teams to Score probabilities sum to 100%"""
        p_none = self._get_prob(ptts, ['None'])
        p_only_home = self._get_prob(ptts, ['Only Home'])
        p_only_away = self._get_prob(ptts, ['Only Away'])
        p_both = self._get_prob(ptts, ['Both teams', 'Both'])
        
        if all([p_none, p_only_home, p_only_away, p_both]):
            total = p_none + p_only_home + p_only_away + p_both
            diff = abs(total - 1.0)
            if diff > 0.05:  # More than 5% off from 100%
                self.contradictions.append(Contradiction(
                    market1="Teams to Score",
                    market2="Mathematical Constraint",
                    description=f"Teams to Score should sum to 100%, but sums to {total:.2%}",
                    expected=1.0,
                    actual=total,
                    difference=diff,
                    severity=self._get_severity(diff)
                ))
    
    def _check_ou_vs_teams_to_score(self, ptts: Dict) -> None:
        """Check Over/Under 0.5 vs Teams to Score: None"""
        p_none = self._get_prob(ptts, ['None'])
        
        # Get Under 0.5 probability
        for name, mp in self.fair_probs.items():
            if 'Over/Under' in name:
                p_under_05 = self._get_prob(mp.probs, ['Under 0.5'])
                if p_under_05 and p_none:
                    # Under 0.5 = 0-0 = Teams to Score: None
                    diff = abs(p_under_05 - p_none)
                    if diff > 0.02:
                        self.contradictions.append(Contradiction(
                            market1="Over/Under 0.5",
                            market2="Teams to Score: None",
                            description=f"Under 0.5={p_under_05:.2%}, but Teams to Score: None={p_none:.2%} (both = 0-0)",
                            expected=p_under_05,
                            actual=p_none,
                            difference=diff,
                            severity=self._get_severity(diff)
                        ))
                    break
    
    def _check_asian_handicap_chain(self) -> None:
        """Check Asian Handicap consistency chain"""
        ah_probs = {}
        
        for name, mp in self.fair_probs.items():
            if 'Asian Handicap' in name:
                if '-0.5' in name:
                    ah_probs['-0.5'] = mp.probs
                elif '-1.5' in name:
                    ah_probs['-1.5'] = mp.probs
                elif '-1' in name and '-1.5' not in name:
                    ah_probs['-1'] = mp.probs
                elif '-2' in name and '-2.5' not in name:
                    ah_probs['-2'] = mp.probs
        
        # AH -0.5 should equal 1X2 Home win
        p1x2 = self.get_1x2_probs()
        if p1x2 and '-0.5' in ah_probs:
            p_home = self._get_prob(p1x2, ['Home', '1'])
            p_ah_home = self._get_prob(ah_probs['-0.5'], ['Home', 'Home (-0.5)'])
            
            if p_home and p_ah_home:
                diff = abs(p_home - p_ah_home)
                if diff > 0.02:
                    self.contradictions.append(Contradiction(
                        market1="1X2 Home",
                        market2="Asian Handicap -0.5 Home",
                        description=f"1X2 Home={p_home:.2%}, but AH-0.5 Home={p_ah_home:.2%} (should be EQUAL)",
                        expected=p_home,
                        actual=p_ah_home,
                        difference=diff,
                        severity=self._get_severity(diff)
                    ))
        
        # AH -1.5 Home <= AH -1 Home <= AH -0.5 Home
        if '-0.5' in ah_probs and '-1' in ah_probs:
            p_05 = self._get_prob(ah_probs['-0.5'], ['Home', 'Home (-0.5)'])
            p_1 = self._get_prob(ah_probs['-1'], ['Home', 'Home (-1.0)', 'Home (-1)'])
            
            if p_05 and p_1 and p_1 > p_05:
                diff = p_1 - p_05
                self.contradictions.append(Contradiction(
                    market1="Asian Handicap -0.5",
                    market2="Asian Handicap -1",
                    description=f"AH-1 Home ({p_1:.2%}) > AH-0.5 Home ({p_05:.2%}) - IMPOSSIBLE!",
                    expected=p_05,
                    actual=p_1,
                    difference=diff,
                    severity="CRITICAL"
                ))
    
    def _check_european_handicap_vs_1x2(self, p1x2: Dict) -> None:
        """Check European Handicap consistency with 1X2"""
        # Handicap 0:1 (Away +1) should relate to score distribution
        # Home (0:1) = Home wins by 2+ goals
        # Draw (0:1) = Home wins by exactly 1
        # Away (0:1) = Draw or Away wins = X2
        
        p_draw = self._get_prob(p1x2, ['Draw', 'X'])
        p_away = self._get_prob(p1x2, ['Away', '2'])
        
        if p_draw and p_away:
            expected_away_01 = p_draw + p_away  # X2
            
            # Find Handicap 0:1 market
            for name, mp in self.fair_probs.items():
                if 'Handicap 0:1' in name:
                    p_h01_away = self._get_prob(mp.probs, ['Away', 'Away (0:1)'])
                    if p_h01_away:
                        diff = abs(expected_away_01 - p_h01_away)
                        if diff > 0.03:
                            self.contradictions.append(Contradiction(
                                market1="1X2 (Draw + Away)",
                                market2="Handicap 0:1 Away",
                                description=f"1X2 implies H(0:1) Away={expected_away_01:.2%}, but actual={p_h01_away:.2%}",
                                expected=expected_away_01,
                                actual=p_h01_away,
                                difference=diff,
                                severity=self._get_severity(diff)
                            ))
                    break
    
    def _get_prob(self, probs: Dict, keys: List[str]) -> Optional[float]:
        """Get probability by trying multiple key variations"""
        for key in keys:
            if key in probs:
                return probs[key]
            # Try case-insensitive
            for k, v in probs.items():
                if key.lower() in k.lower():
                    return v
        return None
    
    def _get_severity(self, diff: float) -> str:
        """Classify severity of contradiction"""
        if diff >= 0.10:
            return "CRITICAL"
        elif diff >= 0.05:
            return "HIGH"
        elif diff >= 0.03:
            return "MEDIUM"
        else:
            return "LOW"
    
    def build_consensus_score_matrix(self) -> Dict[Tuple[int, int], float]:
        """
        Build the most likely score matrix by combining evidence from all markets.
        This is where the "oracle" emerges - finding the truth hidden in the contradictions.
        """
        # Initialize 6x6 matrix (0-5 goals for each team)
        matrix = {}
        for h in range(6):
            for a in range(6):
                matrix[(h, a)] = 0.0
        
        # === Extract all evidence ===
        ou_evidence = self._extract_ou_evidence()
        tts_evidence = self._extract_tts_evidence()
        margin_evidence = self._extract_margin_evidence()
        
        # === Get expected goals from Over/Under analysis ===
        exp_home = 1.3  # default
        exp_away = 1.0  # default
        
        # Try to estimate expected goals from Over/Under probabilities
        for name, mp in self.fair_probs.items():
            if 'Over/Under' in name and 'Early' not in name:
                for outcome, prob in mp.probs.items():
                    if 'Over 2.5' in outcome:
                        # P(Over 2.5) ≈ 1 - Poisson CDF at 2
                        # Rough inverse: if P(O2.5) = 0.55, total goals ≈ 2.8
                        # Formula: exp_total ≈ 2.5 + 2*(prob - 0.5) for prob near 0.5
                        exp_total = max(1.5, min(4.5, 2.5 + 3 * (prob - 0.5)))
                        break
                else:
                    continue
                break
        else:
            exp_total = 2.5  # Default if not found
        
        # Use 1X2 to split expected goals between teams
        p1x2 = self.get_1x2_probs()
        if p1x2:
            p_home = self._get_prob(p1x2, ['Home', '1']) or 0.45
            p_away = self._get_prob(p1x2, ['Away', '2']) or 0.25
            p_draw = self._get_prob(p1x2, ['Draw', 'X']) or 0.30
            
            # Home advantage + relative strength
            # If home more likely to win, they get more expected goals
            total_decisive = p_home + p_away
            if total_decisive > 0:
                home_strength = p_home / total_decisive
            else:
                home_strength = 0.5
            
            # Allocate expected goals
            # Home advantage: home gets slightly more
            exp_home = exp_total * (0.4 + 0.25 * home_strength)
            exp_away = exp_total * (0.35 + 0.25 * (1 - home_strength))
        else:
            exp_home = exp_total * 0.55
            exp_away = exp_total * 0.45
        
        # === Build base Poisson matrix ===
        for h in range(6):
            for a in range(6):
                # Poisson probability
                p_home = (math.exp(-exp_home) * (exp_home ** h)) / math.factorial(h)
                p_away = (math.exp(-exp_away) * (exp_away ** a)) / math.factorial(a)
                matrix[(h, a)] = p_home * p_away
        
        # === Adjust using Teams to Score evidence ===
        if tts_evidence and all(tts_evidence.get(k, 0) > 0 for k in ['none', 'only_home', 'only_away', 'both']):
            p_none = tts_evidence['none']
            p_only_home = tts_evidence['only_home']
            p_only_away = tts_evidence['only_away']
            p_both = tts_evidence['both']
            
            # Current matrix sums for each category
            curr_none = matrix[(0, 0)]
            curr_only_home = sum(matrix[(h, 0)] for h in range(1, 6))
            curr_only_away = sum(matrix[(0, a)] for a in range(1, 6))
            curr_both = sum(matrix[(h, a)] for h in range(1, 6) for a in range(1, 6))
            
            # Scale each category to match TTS probabilities
            if curr_none > 0:
                matrix[(0, 0)] = p_none
            
            if curr_only_home > 0:
                scale = p_only_home / curr_only_home
                for h in range(1, 6):
                    matrix[(h, 0)] *= scale
            
            if curr_only_away > 0:
                scale = p_only_away / curr_only_away
                for a in range(1, 6):
                    matrix[(0, a)] *= scale
            
            if curr_both > 0:
                scale = p_both / curr_both
                for h in range(1, 6):
                    for a in range(1, 6):
                        matrix[(h, a)] *= scale
        
        # === Adjust using win margin evidence from handicaps ===
        if margin_evidence:
            # European Handicap 0:1 tells us about win margins
            p_home_2plus = margin_evidence.get('home_win_2plus', 0)
            p_home_exactly_1 = margin_evidence.get('home_win_exactly_1', 0)
            
            if p_home_2plus > 0 and p_home_exactly_1 > 0:
                # Current matrix values
                curr_home_2plus = sum(matrix[(h, a)] for h in range(6) for a in range(6) if h - a >= 2)
                curr_home_exactly_1 = sum(matrix[(h, a)] for h in range(6) for a in range(6) if h - a == 1)
                
                # Rescale to match handicap evidence
                if curr_home_2plus > 0:
                    scale = p_home_2plus / curr_home_2plus
                    for h in range(6):
                        for a in range(6):
                            if h - a >= 2:
                                matrix[(h, a)] *= scale
                
                if curr_home_exactly_1 > 0:
                    scale = p_home_exactly_1 / curr_home_exactly_1
                    for h in range(6):
                        for a in range(6):
                            if h - a == 1:
                                matrix[(h, a)] *= scale
        
        # === Final normalization ===
        total = sum(matrix.values())
        if total > 0:
            matrix = {k: v / total for k, v in matrix.items()}
        else:
            # Fallback: uniform distribution
            for key in matrix:
                matrix[key] = 1/36
        
        return matrix
    
    def _extract_ou_evidence(self) -> Dict:
        """Extract expected goals from Over/Under markets"""
        evidence = {}
        
        # Find expected goals from O/U line that's closest to 2.0 odds
        for name, mp in self.fair_probs.items():
            if 'Over/Under' in name and 'Early' not in name:
                p_over = self._get_prob(mp.probs, ['Over 2.5'])
                p_under = self._get_prob(mp.probs, ['Under 2.5'])
                
                if p_over and p_under:
                    # If O2.5 is close to 50%, expected goals ≈ 2.5
                    # Adjust based on actual probability
                    evidence['ou25_over'] = p_over
                    evidence['ou25_under'] = p_under
                    
                    # Rough estimate of expected goals
                    # More sophisticated: use all lines to solve
                    if p_over > 0.5:
                        evidence['exp_total'] = 2.5 + (p_over - 0.5) * 2
                    else:
                        evidence['exp_total'] = 2.5 - (0.5 - p_over) * 2
        
        # Try to split between home and away using team-specific data
        p1x2 = self.get_1x2_probs()
        if p1x2:
            p_home = self._get_prob(p1x2, ['Home', '1'])
            p_away = self._get_prob(p1x2, ['Away', '2'])
            
            if p_home and p_away and 'exp_total' in evidence:
                # Allocate expected goals proportionally
                total_decisive = p_home + p_away
                if total_decisive > 0:
                    home_ratio = p_home / total_decisive
                    away_ratio = p_away / total_decisive
                    
                    exp_total = evidence['exp_total']
                    evidence['exp_home'] = exp_total * (0.4 + 0.3 * home_ratio)
                    evidence['exp_away'] = exp_total * (0.4 + 0.3 * away_ratio)
        
        return evidence
    
    def _extract_tts_evidence(self) -> Dict:
        """Extract Teams to Score evidence"""
        evidence = {}
        
        for name, mp in self.fair_probs.items():
            if 'Teams to Score' in name:
                for outcome, prob in mp.probs.items():
                    outcome_lower = outcome.lower()
                    if 'none' in outcome_lower:
                        evidence['none'] = prob
                    elif 'only home' in outcome_lower:
                        evidence['only_home'] = prob
                    elif 'only away' in outcome_lower:
                        evidence['only_away'] = prob
                    elif 'both' in outcome_lower:
                        evidence['both'] = prob
                break
        
        return evidence
    
    def _extract_margin_evidence(self) -> Dict:
        """Extract win margin evidence from handicaps"""
        evidence = {}
        
        # From European Handicap 0:1
        # Home (0:1) = P(win by 2+)
        # Draw (0:1) = P(win by exactly 1)
        
        for name, mp in self.fair_probs.items():
            if 'Handicap 0:1' in name and 'Asian' not in name:
                for outcome, prob in mp.probs.items():
                    outcome_lower = outcome.lower()
                    if 'home' in outcome_lower:
                        evidence['home_win_2plus'] = prob
                    elif 'draw' in outcome_lower:
                        evidence['home_win_exactly_1'] = prob
                    elif 'away' in outcome_lower:
                        evidence['draw_or_away'] = prob
            
            if 'Handicap 1:0' in name and 'Asian' not in name:
                for outcome, prob in mp.probs.items():
                    outcome_lower = outcome.lower()
                    if 'away' in outcome_lower:
                        evidence['away_win_2plus'] = prob
                    elif 'draw' in outcome_lower:
                        evidence['away_win_exactly_1'] = prob
        
        return evidence
    
    def find_oracle_score(self) -> Tuple[int, int, float, Dict]:
        """
        Find the score that the oracle predicts - accounting for all contradictions.
        Returns (home_goals, away_goals, probability, analysis_dict)
        """
        # Build consensus matrix
        matrix = self.build_consensus_score_matrix()
        
        # Find most likely score
        best_score = max(matrix.keys(), key=lambda k: matrix[k])
        best_prob = matrix[best_score]
        
        # Build analysis
        analysis = {
            'matrix': matrix,
            'contradictions': len(self.contradictions),
            'critical_contradictions': sum(1 for c in self.contradictions if c.severity == "CRITICAL"),
            'confidence': self._calculate_confidence()
        }
        
        return best_score[0], best_score[1], best_prob, analysis
    
    def _calculate_confidence(self) -> str:
        """Calculate confidence level based on contradictions"""
        critical = sum(1 for c in self.contradictions if c.severity == "CRITICAL")
        high = sum(1 for c in self.contradictions if c.severity == "HIGH")
        
        if critical >= 2:
            return "LOW - Multiple critical contradictions found"
        elif critical == 1 or high >= 3:
            return "MEDIUM - Some significant contradictions"
        elif high >= 1:
            return "GOOD - Minor contradictions only"
        else:
            return "HIGH - Markets are consistent"
    
    def print_report(self) -> None:
        """Print comprehensive analysis report"""
        print("=" * 80)
        print("🔮 MARKET CONTRADICTION ANALYZER - THE ORACLE SYSTEM 🔮")
        print("=" * 80)
        
        if self.home_team and self.away_team:
            print(f"\n🏠 HOME: {self.home_team}")
            print(f"✈️  AWAY: {self.away_team}")
        
        print(f"\n📊 MARKETS DETECTED: {len(self.markets)}")
        for name, market in self.markets.items():
            margin = self.fair_probs[name].margin if name in self.fair_probs else 0
            if margin > 0:
                print(f"   • {name}: {len(market.outcomes)} outcomes (margin: {margin:.1f}%)")
        
        print("\n" + "=" * 80)
        print("⚠️  CONTRADICTION ANALYSIS")
        print("=" * 80)
        
        if not self.contradictions:
            print("\n✅ No significant contradictions found.")
            print("   The bookmaker's markets are internally consistent.")
        else:
            print(f"\n🚨 Found {len(self.contradictions)} contradiction(s):\n")
            
            # Sort by severity
            sorted_contradictions = sorted(
                self.contradictions,
                key=lambda c: ["LOW", "MEDIUM", "HIGH", "CRITICAL"].index(c.severity),
                reverse=True
            )
            
            for i, c in enumerate(sorted_contradictions, 1):
                severity_emoji = {
                    "CRITICAL": "🔴",
                    "HIGH": "🟠", 
                    "MEDIUM": "🟡",
                    "LOW": "🟢"
                }
                
                print(f"   {i}. [{c.severity}] {severity_emoji[c.severity]}")
                print(f"      Markets: {c.market1} vs {c.market2}")
                print(f"      Issue: {c.description}")
                print(f"      Difference: {c.difference:.2%}")
                print()
        
        # Oracle Prediction
        print("=" * 80)
        print("🔮 ORACLE PREDICTION")
        print("=" * 80)
        
        home_goals, away_goals, prob, analysis = self.find_oracle_score()
        
        print(f"\n   Predicted Score: {home_goals}-{away_goals}")
        print(f"   Probability: {prob:.2%}")
        print(f"   Fair Odds: {1/prob:.2f}" if prob > 0 else "   Fair Odds: N/A")
        print(f"   Confidence: {analysis['confidence']}")
        
        # Top 10 most likely scores
        matrix = analysis['matrix']
        sorted_scores = sorted(matrix.items(), key=lambda x: x[1], reverse=True)[:10]
        
        print("\n   Top 10 Most Likely Scores:")
        for i, ((h, a), p) in enumerate(sorted_scores, 1):
            fair_odds = 1/p if p > 0 else 999
            print(f"      {i:2}. {h}-{a}: {p:.2%} (Fair Odds: {fair_odds:.2f})")
        
        # Match outcome probabilities
        print("\n   Match Outcome Probabilities:")
        p_home_win = sum(p for (h, a), p in matrix.items() if h > a)
        p_draw = sum(p for (h, a), p in matrix.items() if h == a)
        p_away_win = sum(p for (h, a), p in matrix.items() if h < a)
        
        print(f"      Home Win: {p_home_win:.2%}")
        print(f"      Draw:     {p_draw:.2%}")
        print(f"      Away Win: {p_away_win:.2%}")
        
        # Determine winner
        if p_home_win > p_draw and p_home_win > p_away_win:
            winner = self.home_team or "Home"
            winner_prob = p_home_win
        elif p_away_win > p_draw:
            winner = self.away_team or "Away"
            winner_prob = p_away_win
        else:
            winner = "Draw"
            winner_prob = p_draw
        
        print(f"\n   🏆 PREDICTION: {winner}")
        print(f"   📈 WIN PROBABILITY: {winner_prob:.2%}")
        
        # Value Bet Analysis
        print("\n" + "=" * 80)
        print("💰 VALUE BET ANALYSIS")
        print("=" * 80)
        self._analyze_value_bets(matrix, p_home_win, p_draw, p_away_win)
        
        print("\n" + "=" * 80)
    
    def _analyze_value_bets(self, matrix: Dict, p_home: float, p_draw: float, p_away: float) -> None:
        """Analyze potential value bets by comparing our probabilities to bookmaker odds"""
        print("\n   Comparing Oracle probabilities to bookmaker odds:\n")
        
        # Get 1X2 odds
        for name, market in self.markets.items():
            if name == '1X2':
                home_odds = market.outcomes.get('Home', 0)
                draw_odds = market.outcomes.get('Draw', 0)
                away_odds = market.outcomes.get('Away', 0)
                
                if home_odds > 0:
                    implied_prob = 1/home_odds
                    fair_odds = 1/p_home if p_home > 0 else 999
                    edge = (p_home - implied_prob) * 100
                    edge_str = f"+{edge:.1f}%" if edge > 0 else f"{edge:.1f}%"
                    value = "✅ VALUE" if edge > 2 else "❌ NO VALUE"
                    print(f"   HOME WIN:  Odds {home_odds:.2f} (implied {implied_prob:.1%}) vs Oracle {p_home:.1%}")
                    print(f"              Edge: {edge_str} {value}")
                    print()
                
                if draw_odds > 0:
                    implied_prob = 1/draw_odds
                    fair_odds = 1/p_draw if p_draw > 0 else 999
                    edge = (p_draw - implied_prob) * 100
                    edge_str = f"+{edge:.1f}%" if edge > 0 else f"{edge:.1f}%"
                    value = "✅ VALUE" if edge > 2 else "❌ NO VALUE"
                    print(f"   DRAW:      Odds {draw_odds:.2f} (implied {implied_prob:.1%}) vs Oracle {p_draw:.1%}")
                    print(f"              Edge: {edge_str} {value}")
                    print()
                
                if away_odds > 0:
                    implied_prob = 1/away_odds
                    fair_odds = 1/p_away if p_away > 0 else 999
                    edge = (p_away - implied_prob) * 100
                    edge_str = f"+{edge:.1f}%" if edge > 0 else f"{edge:.1f}%"
                    value = "✅ VALUE" if edge > 2 else "❌ NO VALUE"
                    print(f"   AWAY WIN:  Odds {away_odds:.2f} (implied {implied_prob:.1%}) vs Oracle {p_away:.1%}")
                    print(f"              Edge: {edge_str} {value}")
                break


def main():
    """Main function - interactive mode"""
    print("\n" + "=" * 80)
    print("🔮 MARKET CONTRADICTION ANALYZER - THE ORACLE SYSTEM 🔮")
    print("=" * 80)
    print("\nPaste the COMPLETE bookmaker data (all markets), then press Enter twice:\n")
    
    lines = []
    empty_count = 0
    
    while True:
        try:
            line = input()
            if line == "":
                empty_count += 1
                if empty_count >= 2:
                    break
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break
    
    raw_data = '\n'.join(lines)
    
    if not raw_data.strip():
        print("No data provided!")
        return
    
    analyzer = MarketContradictionAnalyzer()
    analyzer.parse_raw_data(raw_data)
    analyzer.analyze_contradictions()
    analyzer.print_report()


if __name__ == "__main__":
    main()
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass