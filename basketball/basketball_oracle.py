#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║      🏀 BASKETBALL MARKET CONTRADICTION ANALYZER - THE ORACLE SYSTEM 🏀       ║
║                                                                               ║
║  Philosophy: The bookmaker prices many markets. Each market is a separate     ║
║  "witness" telling a story about the match. If they DISAGREE, someone made    ║
║  a mistake - and mistakes = edges.                                            ║
║                                                                               ║
║  Basketball-specific checks:                                                  ║
║  • Team Totals must sum to Game Total                                         ║
║  • Moneyline must align with Point Spread                                     ║
║  • Half totals must align with Game Total                                     ║
║  • Quarter totals must be consistent                                          ║
║  • Handicap chain must be monotonic                                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import re
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class MarketData:
    """Holds extracted market data"""
    name: str
    outcomes: Dict[str, float] = field(default_factory=dict)  # outcome -> odds


@dataclass
class Contradiction:
    """Represents a contradiction between markets"""
    market1: str
    market2: str
    description: str
    expected: float
    actual: float
    difference: float
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"


class BasketballOracleAnalyzer:
    """
    Analyzes basketball betting markets to find internal contradictions.
    """
    
    def __init__(self):
        self.markets: Dict[str, MarketData] = {}
        self.contradictions: List[Contradiction] = []
        self.home_team = ""
        self.away_team = ""
        
        # Key extracted values
        self.game_totals: Dict[float, Dict[str, float]] = {}  # line -> {over_prob, under_prob}
        self.home_team_totals: Dict[float, Dict[str, float]] = {}
        self.away_team_totals: Dict[float, Dict[str, float]] = {}
        self.half1_totals: Dict[float, Dict[str, float]] = {}
        self.half2_totals: Dict[float, Dict[str, float]] = {}
        self.spreads: Dict[float, Dict[str, float]] = {}  # spread -> {home_prob, away_prob}
        
        self.moneyline_home_odds = None
        self.moneyline_away_odds = None
        self.moneyline_home_prob = None
        self.moneyline_away_prob = None
    
    def odds_to_prob(self, odds: float) -> float:
        """Convert decimal odds to implied probability"""
        if odds <= 0:
            return 0
        return 1 / odds
    
    def remove_margin_two_way(self, prob1: float, prob2: float) -> Tuple[float, float]:
        """Remove margin from two-way market"""
        total = prob1 + prob2
        if total == 0:
            return (0.5, 0.5)
        return (prob1 / total, prob2 / total)
    
    def calculate_margin(self, odds_list: List[float]) -> float:
        """Calculate bookmaker margin"""
        total_prob = sum(1/odds for odds in odds_list if odds > 0)
        return (total_prob - 1) * 100
    
    def parse_raw_data(self, raw_data: str) -> None:
        """Parse raw bookmaker data"""
        lines = raw_data.strip().split('\n')
        
        # Extract team names from first line
        first_line = lines[0].strip()
        if ' vs ' in first_line or ' v ' in first_line:
            sep = ' vs ' if ' vs ' in first_line else ' v '
            parts = first_line.split(sep)
            if len(parts) >= 2:
                self.home_team = parts[0].strip()
                # Clean up away team name
                away_part = parts[1].strip()
                # Remove trailing stuff like "Change match"
                if 'Change' in away_part:
                    away_part = away_part.split('Change')[0].strip()
                self.away_team = away_part
        
        current_market = None
        market_outcomes = {}
        market_counter = {}
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # Skip navigation/tab lines
            if line in ['All', 'Main', 'Points', 'Half', 'Quarters', 'Specials', 'Players']:
                i += 1
                continue
            
            # Detect market headers (lines with market names)
            if self._is_market_header(line):
                # Save previous market
                if current_market and market_outcomes:
                    self._save_market(current_market, market_outcomes, market_counter)
                
                current_market = line.strip()
                market_outcomes = {}
                i += 1
                continue
            
            # Try to parse outcome with odds
            parsed = self._parse_outcome_line(line)
            if parsed and current_market:
                outcome, odds = parsed
                market_outcomes[outcome] = odds
            
            i += 1
        
        # Save last market
        if current_market and market_outcomes:
            self._save_market(current_market, market_outcomes, market_counter)
        
        # Extract key values for analysis
        self._extract_key_values()
    
    def _save_market(self, market_name: str, outcomes: Dict[str, float], counter: Dict[str, int]) -> None:
        """Save market with duplicate handling"""
        base_name = market_name
        if base_name in counter:
            counter[base_name] += 1
            market_name = f"{base_name}_{counter[base_name]}"
        else:
            counter[base_name] = 1
        
        self.markets[market_name] = MarketData(name=market_name, outcomes=outcomes.copy())
    
    def _is_market_header(self, line: str) -> bool:
        """Check if line is a market header"""
        # Market headers typically don't have odds at the end
        # and contain recognizable market keywords
        
        # Skip if it looks like an outcome line (has odds pattern at end)
        if re.search(r'\d+\.\d+$', line):
            # Check if it's JUST a number (like a line value in header)
            if re.match(r'^[\d.]+$', line):
                return False
            # Could still be header with line number like "Over/Under (incl. overtime) 219.5"
            if not re.match(r'^(Home|Away|Over|Under|Draw|Odd|Even|Yes|No)', line):
                if any(kw in line.lower() for kw in ['over/under', 'handicap', 'winner', 'total', '1x2', 'half', 'quarter']):
                    return True
        
        market_keywords = [
            'winner', 'over/under', 'handicap', 'spread', '1x2', '1X2',
            'quarter', 'half', 'total', 'draw no bet', 'odd/even',
            'race to', 'winning margin', 'asian', 'points', 'assists',
            'rebounds', 'field goals', 'overtime', 'highest scoring',
            'lowest scoring', 'last point', 'free throw'
        ]
        
        line_lower = line.lower()
        
        # Check for market keywords
        for kw in market_keywords:
            if kw in line_lower:
                return True
        
        # Team-specific totals
        if self.home_team and self.home_team.lower() in line_lower:
            if 'over/under' in line_lower or 'total' in line_lower:
                return True
        if self.away_team and self.away_team.lower() in line_lower:
            if 'over/under' in line_lower or 'total' in line_lower:
                return True
        
        return False
    
    def _parse_outcome_line(self, line: str) -> Optional[Tuple[str, float]]:
        """Parse an outcome line and extract outcome name and odds"""
        
        # Pattern 1: "Home1.76" or "Away2.16" or "Draw14.50"
        simple_match = re.match(r'^(Home|Away|Draw|Yes|No|Odd|Even|Equal)([\d.]+)$', line)
        if simple_match:
            outcome = simple_match.group(1)
            try:
                odds = float(simple_match.group(2))
                if 1.01 <= odds <= 500:
                    return (outcome, odds)
            except ValueError:
                pass
        
        # Pattern 2: "Over 219.51.24" - Over/Under with line merged with odds
        ou_match = re.match(r'^(Over|Under)\s*([\d.]+)([\d.]+)$', line)
        if ou_match:
            action = ou_match.group(1)
            # Need to split the number correctly - line.odds
            num_str = ou_match.group(2) + ou_match.group(3)
            # Try different split points
            for split_pos in range(len(num_str) - 2, 1, -1):
                try:
                    line_val = num_str[:split_pos]
                    odds_val = num_str[split_pos:]
                    line_num = float(line_val)
                    odds = float(odds_val)
                    # Valid basketball line is typically 20-300, odds 1.01-50
                    if 1.01 <= odds <= 50 and ((20 <= line_num <= 300) or (0.5 <= line_num <= 70)):
                        return (f"{action} {line_num}", odds)
                except ValueError:
                    continue
        
        # Pattern 3: "Home (-15.5)5.96" - Handicap
        handicap_match = re.match(r'^(Home|Away)\s*\(([+-]?[\d.]+)\)([\d.]+)$', line)
        if handicap_match:
            team = handicap_match.group(1)
            spread = handicap_match.group(2)
            try:
                odds = float(handicap_match.group(3))
                if 1.01 <= odds <= 500:
                    return (f"{team} ({spread})", odds)
            except ValueError:
                pass
        
        # Pattern 4: "Home by 3+2.25" - Winning margin
        margin_match = re.match(r'^(Home|Away)\s+by\s+(\d+\+?)([\d.]+)$', line)
        if margin_match:
            team = margin_match.group(1)
            margin = margin_match.group(2)
            try:
                odds = float(margin_match.group(3))
                if 1.01 <= odds <= 500:
                    return (f"{team} by {margin}", odds)
            except ValueError:
                pass
        
        # Pattern 5: "Other3.60" or "None1.54"
        other_match = re.match(r'^(Other|None|Exact)([\d.]+)$', line)
        if other_match:
            outcome = other_match.group(1)
            try:
                odds = float(other_match.group(2))
                if 1.01 <= odds <= 500:
                    return (outcome, odds)
            except ValueError:
                pass
        
        # Pattern 6: "1st half2.30" or "2nd half1.65"
        half_match = re.match(r'^(1st half|2nd half)([\d.]+)$', line, re.IGNORECASE)
        if half_match:
            outcome = half_match.group(1)
            try:
                odds = float(half_match.group(2))
                if 1.01 <= odds <= 500:
                    return (outcome, odds)
            except ValueError:
                pass
        
        # Pattern 7: Player props "Over 19.51.84" or "Under 19.51.86"
        # Already handled by Pattern 2
        
        # Pattern 8: Team name outcomes like "Minnesota Timberwolves by 6+2.21"
        team_margin = re.match(r'^(.+?)\s+by\s+(\d+\+?)([\d.]+)$', line)
        if team_margin:
            team = team_margin.group(1)
            margin = team_margin.group(2)
            try:
                odds = float(team_margin.group(3))
                if 1.01 <= odds <= 500:
                    return (f"{team} by {margin}", odds)
            except ValueError:
                pass
        
        # Pattern 9: Combined bets like "Minnesota Timberwolves (-2.5) & over 232.53.40"
        combined_match = re.match(r'^(.+?)\s*&\s*(over|under)\s*([\d.]+)([\d.]+)$', line, re.IGNORECASE)
        if combined_match:
            team_spread = combined_match.group(1)
            ou = combined_match.group(2)
            line_num = combined_match.group(3)
            try:
                odds = float(combined_match.group(4))
                if 1.01 <= odds <= 500:
                    return (f"{team_spread} & {ou} {line_num}", odds)
            except ValueError:
                pass
        
        return None
    
    def _extract_key_values(self) -> None:
        """Extract key betting values for analysis"""
        
        for name, market in self.markets.items():
            name_lower = name.lower()
            
            # Main game total (Over/Under incl. overtime without team name)
            if 'over/under' in name_lower and 'incl. overtime' in name_lower:
                if self.home_team.lower() not in name_lower and self.away_team.lower() not in name_lower:
                    if 'half' not in name_lower and 'quarter' not in name_lower:
                        # Extract line from market name
                        line_match = re.search(r'([\d.]+)\s*$', name)
                        if line_match:
                            line = float(line_match.group(1))
                            over_odds = None
                            under_odds = None
                            for outcome, odds in market.outcomes.items():
                                if 'over' in outcome.lower():
                                    over_odds = odds
                                elif 'under' in outcome.lower():
                                    under_odds = odds
                            if over_odds and under_odds:
                                over_prob = self.odds_to_prob(over_odds)
                                under_prob = self.odds_to_prob(under_odds)
                                fair_over, fair_under = self.remove_margin_two_way(over_prob, under_prob)
                                self.game_totals[line] = {'over': fair_over, 'under': fair_under, 
                                                          'over_odds': over_odds, 'under_odds': under_odds}
            
            # Home team total
            if self.home_team.lower() in name_lower and 'over/under' in name_lower:
                if 'half' not in name_lower and 'quarter' not in name_lower:
                    line_match = re.search(r'([\d.]+)\s*$', name)
                    if line_match:
                        line = float(line_match.group(1))
                        over_odds = under_odds = None
                        for outcome, odds in market.outcomes.items():
                            if 'over' in outcome.lower():
                                over_odds = odds
                            elif 'under' in outcome.lower():
                                under_odds = odds
                        if over_odds and under_odds:
                            over_prob, under_prob = self.remove_margin_two_way(
                                self.odds_to_prob(over_odds), self.odds_to_prob(under_odds))
                            self.home_team_totals[line] = {'over': over_prob, 'under': under_prob}
            
            # Away team total
            if self.away_team.lower() in name_lower and 'over/under' in name_lower:
                if 'half' not in name_lower and 'quarter' not in name_lower:
                    line_match = re.search(r'([\d.]+)\s*$', name)
                    if line_match:
                        line = float(line_match.group(1))
                        over_odds = under_odds = None
                        for outcome, odds in market.outcomes.items():
                            if 'over' in outcome.lower():
                                over_odds = odds
                            elif 'under' in outcome.lower():
                                under_odds = odds
                        if over_odds and under_odds:
                            over_prob, under_prob = self.remove_margin_two_way(
                                self.odds_to_prob(over_odds), self.odds_to_prob(under_odds))
                            self.away_team_totals[line] = {'over': over_prob, 'under': under_prob}
            
            # 1st Half totals
            if '1st half' in name_lower and 'over/under' in name_lower:
                for outcome, odds in market.outcomes.items():
                    line_match = re.search(r'([\d.]+)', outcome)
                    if line_match:
                        line = float(line_match.group(1))
                        if line not in self.half1_totals:
                            self.half1_totals[line] = {}
                        if 'over' in outcome.lower():
                            self.half1_totals[line]['over_odds'] = odds
                        elif 'under' in outcome.lower():
                            self.half1_totals[line]['under_odds'] = odds
            
            # 2nd Half totals
            if '2nd half' in name_lower and 'over/under' in name_lower:
                for outcome, odds in market.outcomes.items():
                    line_match = re.search(r'([\d.]+)', outcome)
                    if line_match:
                        line = float(line_match.group(1))
                        if line not in self.half2_totals:
                            self.half2_totals[line] = {}
                        if 'over' in outcome.lower():
                            self.half2_totals[line]['over_odds'] = odds
                        elif 'under' in outcome.lower():
                            self.half2_totals[line]['under_odds'] = odds
            
            # Handicap/Spread
            if 'handicap' in name_lower and 'incl. overtime' in name_lower:
                if 'half' not in name_lower and 'quarter' not in name_lower:
                    # Extract spread from market name
                    spread_match = re.search(r'([+-]?[\d.]+)\s*$', name)
                    if spread_match:
                        spread = float(spread_match.group(1))
                        home_odds = away_odds = None
                        for outcome, odds in market.outcomes.items():
                            if 'home' in outcome.lower():
                                home_odds = odds
                            elif 'away' in outcome.lower():
                                away_odds = odds
                        if home_odds and away_odds:
                            home_prob, away_prob = self.remove_margin_two_way(
                                self.odds_to_prob(home_odds), self.odds_to_prob(away_odds))
                            self.spreads[spread] = {'home': home_prob, 'away': away_prob,
                                                   'home_odds': home_odds, 'away_odds': away_odds}
            
            # Moneyline / Winner
            if 'winner' in name_lower or (name == '1X2' and 'quarter' not in name_lower and 'half' not in name_lower):
                for outcome, odds in market.outcomes.items():
                    if 'home' in outcome.lower():
                        self.moneyline_home_odds = odds
                    elif 'away' in outcome.lower():
                        self.moneyline_away_odds = odds
        
        # Calculate fair moneyline probabilities
        if self.moneyline_home_odds and self.moneyline_away_odds:
            home_prob = self.odds_to_prob(self.moneyline_home_odds)
            away_prob = self.odds_to_prob(self.moneyline_away_odds)
            self.moneyline_home_prob, self.moneyline_away_prob = self.remove_margin_two_way(home_prob, away_prob)
    
    def analyze_contradictions(self) -> List[Contradiction]:
        """Find all market contradictions"""
        self.contradictions = []
        
        # Check 1: Team totals vs Game total
        self._check_team_totals_vs_game_total()
        
        # Check 2: Moneyline vs Spread
        self._check_moneyline_vs_spread()
        
        # Check 3: Half totals vs Game total  
        self._check_half_totals_vs_game_total()
        
        # Check 4: Spread chain consistency
        self._check_spread_chain()
        
        # Check 5: Over/Under chain consistency
        self._check_ou_chain()
        
        # Check 6: Quarter consistency
        self._check_quarter_consistency()
        
        return self.contradictions
    
    def _check_team_totals_vs_game_total(self) -> None:
        """Check if team totals sum to game total"""
        if not self.home_team_totals or not self.away_team_totals or not self.game_totals:
            return
        
        # Use median lines for comparison
        home_lines = sorted(self.home_team_totals.keys())
        away_lines = sorted(self.away_team_totals.keys())
        game_lines = sorted(self.game_totals.keys())
        
        if not home_lines or not away_lines or not game_lines:
            return
        
        # Get middle lines (where over/under is ~50%)
        home_mid = home_lines[len(home_lines)//2]
        away_mid = away_lines[len(away_lines)//2]
        game_mid = game_lines[len(game_lines)//2]
        
        expected_game_total = home_mid + away_mid
        diff = abs(expected_game_total - game_mid)
        
        if diff > 3:  # More than 3 points off
            self.contradictions.append(Contradiction(
                market1="Team Totals",
                market2="Game Total",
                description=f"Team totals ({home_mid} + {away_mid} = {expected_game_total}) vs Game Total line ({game_mid})",
                expected=expected_game_total,
                actual=game_mid,
                difference=diff,
                severity=self._get_severity_points(diff)
            ))
    
    def _check_moneyline_vs_spread(self) -> None:
        """Check if moneyline aligns with spread"""
        if not self.moneyline_home_prob or not self.spreads:
            return
        
        # Find the spread closest to 50/50
        closest_spread = None
        closest_diff = 1.0
        for spread, probs in self.spreads.items():
            diff = abs(probs['home'] - 0.5)
            if diff < closest_diff:
                closest_diff = diff
                closest_spread = spread
        
        if closest_spread is None:
            return
        
        # Estimate expected moneyline prob from spread
        # Rough rule: each point of spread ≈ 2.7% probability shift
        # Spread of -5 means home needs to win by 5+, so moneyline home should be higher
        spread_implied_ml = 0.5 + (abs(closest_spread) * 0.027)
        if closest_spread > 0:  # Home is underdog
            spread_implied_ml = 0.5 - (closest_spread * 0.027)
        
        spread_implied_ml = max(0.1, min(0.9, spread_implied_ml))
        
        diff = abs(self.moneyline_home_prob - spread_implied_ml)
        
        if diff > 0.10:  # More than 10% difference
            self.contradictions.append(Contradiction(
                market1="Moneyline",
                market2=f"Spread {closest_spread}",
                description=f"Moneyline implies {self.moneyline_home_prob:.1%} home win, spread suggests ~{spread_implied_ml:.1%}",
                expected=spread_implied_ml,
                actual=self.moneyline_home_prob,
                difference=diff,
                severity=self._get_severity(diff)
            ))
    
    def _check_half_totals_vs_game_total(self) -> None:
        """Check if half totals are consistent with game total"""
        if not self.half1_totals or not self.half2_totals or not self.game_totals:
            return
        
        # Get median lines
        h1_lines = sorted(self.half1_totals.keys())
        h2_lines = sorted(self.half2_totals.keys())
        game_lines = sorted(self.game_totals.keys())
        
        if not h1_lines or not h2_lines or not game_lines:
            return
        
        h1_mid = h1_lines[len(h1_lines)//2]
        h2_mid = h2_lines[len(h2_lines)//2]
        game_mid = game_lines[len(game_lines)//2]
        
        expected = h1_mid + h2_mid
        diff = abs(expected - game_mid)
        
        if diff > 5:  # More than 5 points
            self.contradictions.append(Contradiction(
                market1="Half Totals",
                market2="Game Total",
                description=f"Half totals ({h1_mid} + {h2_mid} = {expected}) vs Game Total ({game_mid})",
                expected=expected,
                actual=game_mid,
                difference=diff,
                severity=self._get_severity_points(diff)
            ))
    
    def _check_spread_chain(self) -> None:
        """Check spread probability chain is monotonic"""
        if len(self.spreads) < 2:
            return
        
        # Sort by spread value (most negative first)
        sorted_spreads = sorted(self.spreads.items(), key=lambda x: x[0])
        
        for i in range(len(sorted_spreads) - 1):
            spread1, probs1 = sorted_spreads[i]
            spread2, probs2 = sorted_spreads[i + 1]
            
            # Home covering smaller spread should have higher prob
            if spread1 < spread2:  # Both negative, spread1 is harder
                if probs1['home'] > probs2['home'] + 0.03:
                    diff = probs1['home'] - probs2['home']
                    self.contradictions.append(Contradiction(
                        market1=f"Spread {spread1}",
                        market2=f"Spread {spread2}",
                        description=f"Home {spread1} ({probs1['home']:.1%}) > Home {spread2} ({probs2['home']:.1%}) - IMPOSSIBLE",
                        expected=probs2['home'],
                        actual=probs1['home'],
                        difference=diff,
                        severity="CRITICAL"
                    ))
    
    def _check_ou_chain(self) -> None:
        """Check Over/Under probability chain"""
        if len(self.game_totals) < 2:
            return
        
        sorted_lines = sorted(self.game_totals.items(), key=lambda x: x[0])
        
        for i in range(len(sorted_lines) - 1):
            line1, probs1 = sorted_lines[i]
            line2, probs2 = sorted_lines[i + 1]
            
            # Over probability should decrease as line increases
            if probs2['over'] > probs1['over'] + 0.02:
                diff = probs2['over'] - probs1['over']
                self.contradictions.append(Contradiction(
                    market1=f"Over {line1}",
                    market2=f"Over {line2}",
                    description=f"Over {line2} ({probs2['over']:.1%}) > Over {line1} ({probs1['over']:.1%}) - IMPOSSIBLE",
                    expected=probs1['over'],
                    actual=probs2['over'],
                    difference=diff,
                    severity="CRITICAL"
                ))
    
    def _check_quarter_consistency(self) -> None:
        """Check quarter markets for consistency"""
        # This can be expanded with quarter-specific data
        pass
    
    def _get_severity(self, diff: float) -> str:
        """Classify severity (probability-based)"""
        if diff >= 0.10:
            return "CRITICAL"
        elif diff >= 0.06:
            return "HIGH"
        elif diff >= 0.04:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _get_severity_points(self, diff: float) -> str:
        """Classify severity (points-based)"""
        if diff >= 8:
            return "CRITICAL"
        elif diff >= 5:
            return "HIGH"
        elif diff >= 3:
            return "MEDIUM"
        else:
            return "LOW"
    
    def calculate_expected_total(self) -> float:
        """Calculate expected game total from O/U lines"""
        if not self.game_totals:
            return 220  # Default
        
        # Find line closest to 50/50
        best_line = None
        best_diff = 1.0
        for line, probs in self.game_totals.items():
            diff = abs(probs['over'] - 0.5)
            if diff < best_diff:
                best_diff = diff
                best_line = line
        
        return best_line if best_line else 220
    
    def calculate_expected_scores(self) -> Tuple[float, float]:
        """Calculate expected score for each team"""
        total = self.calculate_expected_total()
        
        # If we have team totals, use median
        if self.home_team_totals:
            home_lines = sorted(self.home_team_totals.keys())
            home_exp = home_lines[len(home_lines)//2]
        else:
            # Estimate from moneyline - favorite scores slightly more
            home_share = 0.5
            if self.moneyline_home_prob:
                home_share = 0.48 + (self.moneyline_home_prob - 0.5) * 0.1
            home_exp = total * home_share
        
        if self.away_team_totals:
            away_lines = sorted(self.away_team_totals.keys())
            away_exp = away_lines[len(away_lines)//2]
        else:
            away_exp = total - home_exp
        
        return (home_exp, away_exp)
    
    def find_value_bets(self) -> Dict[str, Dict]:
        """Find value bets"""
        value_bets = {}
        
        if self.moneyline_home_prob and self.moneyline_home_odds:
            implied = self.odds_to_prob(self.moneyline_home_odds)
            edge = (self.moneyline_home_prob - implied) * 100
            value_bets['HOME'] = {
                'odds': self.moneyline_home_odds,
                'implied': implied,
                'oracle': self.moneyline_home_prob,
                'edge': edge,
                'has_value': edge > 2
            }
        
        if self.moneyline_away_prob and self.moneyline_away_odds:
            implied = self.odds_to_prob(self.moneyline_away_odds)
            edge = (self.moneyline_away_prob - implied) * 100
            value_bets['AWAY'] = {
                'odds': self.moneyline_away_odds,
                'implied': implied,
                'oracle': self.moneyline_away_prob,
                'edge': edge,
                'has_value': edge > 2
            }
        
        # Check O/U value
        if self.game_totals:
            # Get the main line (closest to 50/50)
            main_line = None
            best_diff = 1.0
            for line, probs in self.game_totals.items():
                diff = abs(probs['over'] - 0.5)
                if diff < best_diff:
                    best_diff = diff
                    main_line = line
            
            if main_line and 'over_odds' in self.game_totals[main_line]:
                over_odds = self.game_totals[main_line]['over_odds']
                over_prob = self.game_totals[main_line]['over']
                implied = self.odds_to_prob(over_odds)
                edge = (over_prob - implied) * 100
                value_bets[f'OVER {main_line}'] = {
                    'odds': over_odds,
                    'implied': implied,
                    'oracle': over_prob,
                    'edge': edge,
                    'has_value': edge > 2
                }
                
                under_odds = self.game_totals[main_line]['under_odds']
                under_prob = self.game_totals[main_line]['under']
                implied = self.odds_to_prob(under_odds)
                edge = (under_prob - implied) * 100
                value_bets[f'UNDER {main_line}'] = {
                    'odds': under_odds,
                    'implied': implied,
                    'oracle': under_prob,
                    'edge': edge,
                    'has_value': edge > 2
                }
        
        return value_bets
    
    def get_recommendation(self) -> str:
        """Generate betting recommendation"""
        value_bets = self.find_value_bets()
        
        # Prediction
        if self.moneyline_home_prob and self.moneyline_away_prob:
            if self.moneyline_home_prob > self.moneyline_away_prob:
                prediction = 'HOME'
                pred_name = self.home_team or 'Home'
            else:
                prediction = 'AWAY'
                pred_name = self.away_team or 'Away'
        else:
            prediction = 'HOME'
            pred_name = self.home_team or 'Home'
        
        # Check if prediction has value
        if prediction in value_bets and value_bets[prediction]['has_value']:
            edge = value_bets[prediction]['edge']
            odds = value_bets[prediction]['odds']
            return f"🎯 BET {pred_name.upper()} @ {odds:.2f} - Prediction + Value ALIGN (+{edge:.1f}% edge) ✅"
        
        # Check for strong value anywhere
        for outcome, data in value_bets.items():
            if data['edge'] >= 5:
                return f"💰 VALUE BET: {outcome} @ {data['odds']:.2f} (+{data['edge']:.1f}% edge)"
        
        # Check for moderate value
        for outcome, data in value_bets.items():
            if 3 <= data['edge'] < 5:
                return f"⚠️ SMALL VALUE: {outcome} @ {data['odds']:.2f} (+{data['edge']:.1f}% edge) - Consider small bet"
        
        return "⏭️ SKIP - No significant value found"
    
    def print_report(self) -> None:
        """Print analysis report"""
        print("\n" + "=" * 80)
        print("🏀 BASKETBALL ORACLE - MARKET CONTRADICTION ANALYZER 🏀")
        print("=" * 80)
        
        if self.home_team and self.away_team:
            print(f"\n🏠 HOME: {self.home_team}")
            print(f"✈️  AWAY: {self.away_team}")
        
        print(f"\n📊 MARKETS DETECTED: {len(self.markets)}")
        
        # Key data summary
        if self.game_totals:
            lines = sorted(self.game_totals.keys())
            print(f"   • Game Total Lines: {lines[0]} to {lines[-1]} ({len(lines)} lines)")
        if self.home_team_totals:
            lines = sorted(self.home_team_totals.keys())
            print(f"   • {self.home_team} Total Lines: {lines[0]} to {lines[-1]}")
        if self.away_team_totals:
            lines = sorted(self.away_team_totals.keys())
            print(f"   • {self.away_team} Total Lines: {lines[0]} to {lines[-1]}")
        if self.spreads:
            spreads = sorted(self.spreads.keys())
            print(f"   • Spread Lines: {spreads[0]} to {spreads[-1]} ({len(spreads)} lines)")
        if self.moneyline_home_odds:
            print(f"   • Moneyline: Home {self.moneyline_home_odds:.2f} / Away {self.moneyline_away_odds:.2f}")
        
        # Contradictions
        print("\n" + "=" * 80)
        print("⚠️  CONTRADICTION ANALYSIS")
        print("=" * 80)
        
        if not self.contradictions:
            print("\n✅ No significant contradictions found.")
            print("   The bookmaker's markets are internally consistent.")
        else:
            print(f"\n🚨 Found {len(self.contradictions)} contradiction(s):\n")
            
            severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            sorted_c = sorted(self.contradictions, 
                            key=lambda c: severity_order.index(c.severity))
            
            emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
            
            for i, c in enumerate(sorted_c, 1):
                print(f"   {i}. [{c.severity}] {emoji[c.severity]}")
                print(f"      Markets: {c.market1} vs {c.market2}")
                print(f"      Issue: {c.description}")
                print()
        
        # Prediction
        print("=" * 80)
        print("🏀 ORACLE PREDICTION")
        print("=" * 80)
        
        home_exp, away_exp = self.calculate_expected_scores()
        total_exp = self.calculate_expected_total()
        
        print(f"\n   Expected Score: {self.home_team or 'Home'} {home_exp:.0f} - {away_exp:.0f} {self.away_team or 'Away'}")
        print(f"   Expected Total: {total_exp:.0f} points")
        
        if self.moneyline_home_prob and self.moneyline_away_prob:
            print(f"\n   Win Probabilities:")
            print(f"      {self.home_team or 'Home'}: {self.moneyline_home_prob:.1%}")
            print(f"      {self.away_team or 'Away'}: {self.moneyline_away_prob:.1%}")
            
            if self.moneyline_home_prob > self.moneyline_away_prob:
                winner = self.home_team or "Home"
                winner_prob = self.moneyline_home_prob
            else:
                winner = self.away_team or "Away"
                winner_prob = self.moneyline_away_prob
            
            print(f"\n   🏆 PREDICTION: {winner}")
            print(f"   📈 WIN PROBABILITY: {winner_prob:.1%}")
        
        # Value analysis
        print("\n" + "=" * 80)
        print("💰 VALUE BET ANALYSIS")
        print("=" * 80)
        
        value_bets = self.find_value_bets()
        print("\n   Comparing Oracle probabilities to bookmaker odds:\n")
        
        for outcome, data in value_bets.items():
            if outcome == 'HOME':
                name = self.home_team or 'Home'
            elif outcome == 'AWAY':
                name = self.away_team or 'Away'
            else:
                name = outcome
            
            edge_str = f"+{data['edge']:.1f}%" if data['edge'] > 0 else f"{data['edge']:.1f}%"
            value_ind = "✅ VALUE" if data['has_value'] else "❌ NO VALUE"
            
            print(f"   {name.upper()}:")
            print(f"      Odds: {data['odds']:.2f} (implied {data['implied']:.1%})")
            print(f"      Oracle: {data['oracle']:.1%}")
            print(f"      Edge: {edge_str} {value_ind}")
            print()
        
        # Recommendation
        print("=" * 80)
        print("🎯 RECOMMENDED ACTION")
        print("=" * 80)
        print(f"\n   {self.get_recommendation()}")
        
        print("\n" + "=" * 80)


def main():
    """Main function"""
    print("\n" + "=" * 80)
    print("🏀 BASKETBALL ORACLE - MARKET CONTRADICTION ANALYZER 🏀")
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
    
    analyzer = BasketballOracleAnalyzer()
    analyzer.parse_raw_data(raw_data)
    analyzer.analyze_contradictions()
    analyzer.print_report()


if __name__ == "__main__":
    main()
    try:
        input("\nPress Enter to exit...")
    except EOFError:
        pass