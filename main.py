#!/usr/bin/env python3
"""
Roblox Up-and-Coming Forecast - make.fun bounty
Predicts top 10 games for 72 hours based on hourly chart snapshots.

Input: /input/chart_history.json (or similar)
Output: /output/forecast.json
"""

import json
import os
import math
from collections import defaultdict
from typing import Dict, List, Any

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
    snapshots.sort(key=lambda x: x.get('timestamp', x.get('time', '')))
    return snapshots

def extract_game_stats(snapshots: List[Dict]) -> Dict[str, Dict]:
    """Extract statistics for each game from snapshots."""
    game_data = defaultdict(lambda: {
        'names': set(),
        'ranks': [],
        'players': [],
        'appearances': 0
    })
    
    for snap in snapshots:
        time = snap.get('timestamp', snap.get('time', ''))
        games = snap.get('games', snap.get('data', []))
        
        for game in games:
            name = game.get('name', game.get('game_name', ''))
            rank = game.get('rank', game.get('place', 999))
            players = game.get('players', game.get('player_count', 0))
            
            if name:
                game_data[name]['names'].add(name)
                game_data[name]['ranks'].append(rank)
                game_data[name]['players'].append(players)
                game_data[name]['appearances'] += 1
    
    return game_data

def predict_top_10(snapshots: List[Dict], game_data: Dict) -> List[Dict]:
    """
    Predict top 10 games for each of 72 hours using multiple factors:
    - Recent rank momentum
    - Player count trend
    - Consistency
    - Recency weighting
    """
    if not snapshots:
        return []
    
    # Get the most recent snapshot
    latest = snapshots[-1]
    latest_games = latest.get('games', latest.get('data', []))
    
    # Calculate momentum for each game
    game_momentum = {}
    
    for game_name, stats in game_data.items():
        if stats['appearances'] < 2:
            continue
            
        ranks = stats['ranks']
        players = stats['players']
        
        # Recent rank trend (last 5 snapshots)
        recent_ranks = ranks[-5:] if len(ranks) >= 5 else ranks
        recent_players = players[-5:] if len(players) >= 5 else players
        
        # Rank improvement (lower is better)
        if len(recent_ranks) >= 2:
            rank_change = recent_ranks[0] - recent_ranks[-1]  # Positive = improving
        else:
            rank_change = 0
            
        # Player growth
        if len(recent_players) >= 2 and recent_players[-1] > 0:
            player_growth = (recent_players[-1] - recent_players[0]) / recent_players[0]
        else:
            player_growth = 0
        
        # Current rank (lower is better)
        current_rank = recent_ranks[-1] if recent_ranks else 999
        
        # Calculate score: prioritize rising games with good current rank
        score = 0
        score += max(0, rank_change) * 2  # Momentum
        score += player_growth * 1000  # Growth
        score += max(0, 100 - current_rank) * 0.5  # Current position
        
        game_momentum[game_name] = {
            'score': score,
            'current_rank': current_rank,
            'recent_ranks': recent_ranks,
            'player_growth': player_growth
        }
    
    # Get top games by score
    sorted_games = sorted(game_momentum.items(), key=lambda x: x[1]['score'], reverse=True)
    
    # Generate forecasts for 72 hours
    forecasts = []
    
    for hour in range(72):
        hour_forecast = {
            "hour": hour,
            "predictions": []
        }
        
        # For each hour, slightly adjust based on trends
        # Games with strong momentum maintain/gain position
        # Games with weak momentum fall
        
        for i, (game_name, data) in enumerate(sorted_games[:20]):  # Consider top 20
            if i >= 10:
                break
                
            # Probability based on position confidence
            # Higher rank = higher probability
            rank_confidence = max(0, 1 - (data['current_rank'] / 100))
            
            # Add some decay for longer forecasts
            decay = 1 - (hour * 0.003)  # Slight decay over time
            
            probability = min(0.95, rank_confidence * decay * 0.8 + 0.2)
            
            hour_forecast['predictions'].append({
                "rank": i + 1,
                "name": game_name,
                "probability": round(probability, 4),
                "estimated_players": max(0, data.get('recent_players', [0])[-1] if data.get('recent_players') else 0)
            })
        
        forecasts.append(hour_forecast)
    
    return forecasts

def main():
    # Load input data
    snapshots = load_input()
    
    if not snapshots:
        # Create empty forecast if no data
        forecast = {
            "forecast": []
        }
    else:
        # Extract game statistics
        game_data = extract_game_stats(snapshots)
        
        # Generate predictions
        predictions = predict_top_10(snapshots, game_data)
        
        forecast = {
            "forecast": predictions,
            "model": "momentum-rank-forecaster",
            "generated_at": snapshots[-1].get('timestamp', ''),
            "input_snapshots": len(snapshots)
        }
    
    # Ensure output directory exists
    os.makedirs("/output", exist_ok=True)
    
    # Write forecast
    with open("/output/forecast.json", "w") as f:
        json.dump(forecast, f, indent=2)
    
    print(f"Forecast written to /output/forecast.json")
    print(f"Generated {len(forecast.get('forecast', []))} predictions")

if __name__ == "__main__":
    main()
