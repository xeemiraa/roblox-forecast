#!/usr/bin/env python3
"""
Roblox Up-and-Coming Forecast - make.fun bounty
Predicts top 10 games for 72 hours based on hourly chart snapshots.

Uses multi-factor analysis:
- Player count momentum (growth rate)
- Rank velocity (how fast climbing)
- Game age/recency
- Volatility-adjusted confidence
"""

import json
import os
import math
from collections import defaultdict
from typing import Dict, List, Any, Optional

def load_input() -> List[Dict]:
    """Load chart history from /input directory."""
    input_dir = "/input"
    files = sorted(os.listdir(input_dir))
    
    snapshots = []
    for fname in files:
        if fname.endswith('.json'):
            with open(os.path.join(input_dir, fname)) as f:
                data = json.load(f)
                if isinstance(data, list):
                    snapshots.extend(data)
                else:
                    snapshots.append(data)
    
    # Sort by timestamp
    snapshots.sort(key=lambda x: x.get('timestamp', x.get('time', x.get('date', ''))))
    return snapshots

def parse_snapshot(snap: Dict) -> tuple:
    """Parse a snapshot to get timestamp and games list."""
    time = snap.get('timestamp', snap.get('time', snap.get('date', snap.get('hour', ''))))
    games = snap.get('games', snap.get('data', snap.get('chart', [])))
    return time, games

def extract_features(snapshots: List[Dict]) -> Dict[str, Dict]:
    """
    Extract features for each game from snapshots.
    Features: rank history, player history, age, volatility
    """
    game_features = defaultdict(lambda: {
        'ranks': [],
        'players': [],
        'timestamps': [],
        'first_seen': None,
        'last_seen': None,
        'name_variants': set()
    })
    
    for snap in snapshots:
        time, games = parse_snapshot(snap)
        
        for game in games:
            name = game.get('name', game.get('game_name', game.get('title', '')))
            rank = game.get('rank', game.get('place', game.get('position', 999)))
            players = game.get('players', game.get('player_count', game.get('active_players', 0)))
            
            if not name:
                continue
                
            game_features[name]['name_variants'].add(name)
            game_features[name]['ranks'].append(rank)
            game_features[name]['players'].append(players)
            game_features[name]['timestamps'].append(time)
            
            if game_features[name]['first_seen'] is None:
                game_features[name]['first_seen'] = time
            game_features[name]['last_seen'] = time
    
    return game_features

def compute_growth_rate(players: List[float]) -> float:
    """Compute average growth rate from player history."""
    if len(players) < 2:
        return 0
    
    # Use recent growth (last few data points)
    recent = players[-5:] if len(players) >= 5 else players
    
    if recent[-1] <= 0:
        return -1  # Declining
    
    # Average growth rate
    growths = []
    for i in range(1, len(recent)):
        if recent[i-1] > 0:
            growth = (recent[i] - recent[i-1]) / recent[i-1]
            growths.append(growth)
    
    if not growths:
        return 0
    
    return sum(growths) / len(growths)

def compute_rank_velocity(ranks: List[int]) -> float:
    """
    Compute how fast a game is climbing (positive = improving).
    Recent velocity matters more.
    """
    if len(ranks) < 2:
        return 0
    
    recent = ranks[-5:] if len(ranks) >= 5 else ranks
    
    velocities = []
    for i in range(1, len(recent)):
        # Lower rank number = better, so negative change = improving
        vel = recent[i-1] - recent[i]
        velocities.append(vel)
    
    if not velocities:
        return 0
    
    # Weight recent more heavily
    weights = list(range(1, len(velocities) + 1))
    weighted_sum = sum(v * w for v, w in zip(velocities, weights))
    weight_sum = sum(weights)
    
    return weighted_sum / weight_sum if weight_sum > 0 else 0

def score_game(name: str, features: Dict) -> float:
    """
    Score a game for forecasting.
    Higher score = more likely to be in top 10.
    """
    ranks = features['ranks']
    players = features['players']
    
    if not ranks or not players:
        return -1000
    
    current_rank = ranks[-1]
    current_players = players[-1]
    
    # Must have players to be viable
    if current_players <= 0:
        return -1000
    
    # Base score from current rank (lower is better)
    rank_score = max(0, 1000 - current_rank * 100)
    
    # Growth rate score
    growth = compute_growth_rate(players)
    growth_score = growth * 5000 if growth > 0 else growth * 1000
    
    # Rank velocity score
    velocity = compute_rank_velocity(ranks)
    velocity_score = velocity * 200
    
    # Consistency bonus (games that stay in chart)
    consistency = min(1, features['appearances'] / 50) if 'appearances' in features else 0.5
    consistency_score = consistency * 100
    
    # Recency bonus (newer games have more potential)
    total_snapshots = len(ranks)
    recency = total_snapshots / 100  # Normalize
    recency_score = recency * 50
    
    total = rank_score + growth_score + velocity_score + consistency_score + recency_score
    
    return total

def generate_forecast(snapshots: List[Dict], game_features: Dict) -> Dict:
    """
    Generate forecast for 72 hours.
    Returns forecast.json structure.
    """
    if not snapshots or not game_features:
        return {
            "forecast": [],
            "note": "No input data available"
        }
    
    # Score all games
    scored_games = []
    for name, features in game_features.items():
        score = score_game(name, features)
        if score > -1000:
            scored_games.append({
                'name': name,
                'score': score,
                'current_rank': features['ranks'][-1] if features['ranks'] else 999,
                'current_players': features['players'][-1] if features['players'] else 0,
                'growth': compute_growth_rate(features['players']),
                'velocity': compute_rank_velocity(features['ranks']),
                'appearances': len(features['ranks'])
            })
    
    # Sort by score
    scored_games.sort(key=lambda x: x['score'], reverse=True)
    
    # Generate 72 hourly forecasts
    forecasts = []
    
    for hour in range(72):
        hour_pred = {
            "hour": hour,
            "read_timestamp": f"2026-11-13T06:00:00Z",  # Will be adjusted
            "top_10": []
        }
        
        # For each position, assign probabilities
        for position in range(10):
            if position < len(scored_games):
                game = scored_games[position]
                
                # Probability based on:
                # - Position confidence (higher position = higher prob)
                # - Score gap to next game
                # - Growth trajectory
                # - Uncertainty increases with forecast horizon
                
                position_confidence = 1.0 - (position * 0.08)
                
                # Decay over time
                time_decay = math.exp(-hour * 0.005)
                
                # Growth adjustment
                growth_boost = max(0, game['growth'] * 10)
                
                # Calculate probability
                base_prob = 0.25  # Minimum probability
                prob = (position_confidence * 0.5 + growth_boost * 0.3 + base_prob) * time_decay
                prob = max(0.01, min(0.95, prob))
                
                hour_pred['top_10'].append({
                    "rank": position + 1,
                    "name": game['name'],
                    "probability": round(prob, 6),
                    "estimated_players": round(game['current_players'] * (1 + game['growth'] * hour * 0.01))
                })
            else:
                # Fill remaining positions with low probability
                hour_pred['top_10'].append({
                    "rank": position + 1,
                    "name": "unknown",
                    "probability": 0.01,
                    "estimated_players": 0
                })
        
        forecasts.append(hour_pred)
    
    return {
        "forecast": forecasts,
        "model": "multi-factor-rank-forecaster-v1",
        "total_games_analyzed": len(scored_games),
        "generated_from": len(snapshots),
        "scored_games": [g['name'] for g in scored_games[:20]]
    }

def main():
    print("Loading input data...")
    snapshots = load_input()
    print(f"Loaded {len(snapshots)} snapshots")
    
    if not snapshots:
        print("No snapshots found, creating empty forecast")
        forecast = {"forecast": []}
    else:
        print("Extracting game features...")
        game_features = extract_features(snapshots)
        print(f"Found {len(game_features)} unique games")
        
        print("Generating forecast...")
        forecast = generate_forecast(snapshots, game_features)
        print(f"Generated {len(forecast.get('forecast', []))} hourly predictions")
    
    # Ensure output directory exists
    os.makedirs("/output", exist_ok=True)
    
    # Write forecast
    output_path = "/output/forecast.json"
    with open(output_path, "w") as f:
        json.dump(forecast, f, indent=2)
    
    print(f"Forecast written to {output_path}")
    
    # Print summary
    if forecast.get('forecast'):
        first_pred = forecast['forecast'][0]
        print(f"\nFirst hour prediction (hour 0):")
        for item in first_pred.get('top_10', [])[:5]:
            print(f"  #{item['rank']}: {item['name']} (prob: {item['probability']:.4f})")

if __name__ == "__main__":
    main()
