from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import pygambit
import random

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]


def simulate_dealer(dealer_total):
    """Simulates dealer's play and returns probability distribution of final outcomes"""
    outcomes = {}

    def dealer_play(hand):
        card_values = {'J': 10, 'Q': 10, 'K': 10, 'A': 11}  # Adjust Ace handling separately

        hand = [card_values[card] if card in card_values else int(card) for card in hand]
        total = sum(hand)

        soft_ace_count = hand.count(11)

        # Adjust for aces if over 21
        while total > 21 and soft_ace_count:
            total -= 10
            soft_ace_count -= 1

        # Dealer stands at 17+
        if total >= 17:
            outcomes[total] = outcomes.get(total, 0) + 1
            return

        # Draw next card
        for card in deck:
            dealer_play(hand + [card])

    dealer_play([dealer_total])

    # Convert to probability distribution
    total_sims = sum(outcomes.values())
    return {k: v / total_sims for k, v in outcomes.items()}

# Compute EV if the player stands
def ev_stand(player_total, dealer_card):
    dealer_outcomes = simulate_dealer(dealer_card)

    ev = sum(
        prob * (1 if player_total > dealer_total else -1 if player_total < dealer_total else 0)
        for dealer_total, prob in dealer_outcomes.items()
    )
    return ev

# Compute EV if the player hits
def ev_hit(player_total, dealer_card):
    ev = 0
    for new_card in deck:
        new_total = player_total + new_card

        if new_total > 21:
            ev += -1 / len(deck)  # Bust → immediate loss
        else:
            ev += ev_stand(new_total, dealer_card) / len(deck)

    return ev


# Create game theory models for different blackjack scenarios
def simulate_blackjack(player_total, dealer_upcard, num_simulations=100000):
    """ Simulates blackjack hands to generate the payoff matrix. """
    
    def dealer_final_hand(dealer_start):
        """ Simulates the dealer's play based on standard blackjack rules. """
        while dealer_start < 17:  # Dealer hits until 17 or more
            dealer_start += random.choice(deck)  # Draw a card
            if dealer_start > 21:
                return -1  # Dealer busts
        return dealer_start  # Dealer's final hand

    def simulate_hand(player_action):
        """ Simulates a single round based on player action (Hit or Stand). """
        player_hand = player_total
        dealer_hand = dealer_final_hand(dealer_upcard)

        if player_action == "Hit":
            player_hand += random.choice(deck)  # Player takes a hit
            if player_hand > 21:
                return -1  # Player busts and loses immediately

        if dealer_hand == -1:  # Dealer busts
            return 1  # Player wins
        
        if player_hand > dealer_hand:
            return 1  # Player wins
        elif player_hand < dealer_hand:
            return -1  # Player loses
        else:
            return 0  # Push (tie)

    deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]  # Standard card values
    
    results = {"Stand": [], "Hit": []}
    
    for _ in range(num_simulations):
        results["Stand"].append(simulate_hand("Stand"))
        results["Hit"].append(simulate_hand("Hit"))

    def calculate_ev(results):
        """ Computes the probabilities and EV from simulation results. """
        wins = results.count(1)
        losses = results.count(-1)
        pushes = results.count(0)
        total = len(results)
        win_prob = wins / total
        loss_prob = losses / total
        push_prob = pushes / total
        ev = win_prob - loss_prob  # EV = Win% - Lose%
        return win_prob, loss_prob, push_prob, ev

    stand_win, stand_loss, stand_push, ev_stand = calculate_ev(results["Stand"])
    hit_win, hit_loss, hit_push, ev_hit = calculate_ev(results["Hit"])

    return ev_stand, ev_hit

def compute_nash_equilibrium(ev_stand, ev_hit):
    """ Compute Nash Equilibrium for the player's Hit/Stand decision. """
    player_payoffs = [
        [ev_stand, ev_stand],  # Player chooses Stand
        [ev_hit, ev_hit]  # Player chooses Hit
    ]
    
    dealer_payoffs = [
        [-ev_stand, -ev_stand],  # Dealer loses what Player gains
        [-ev_hit, -ev_hit]  # Dealer loses what Player gains
    ]
    
    lgame = (player_payoffs, dealer_payoffs)
    

    # Convert the matrix to a Gambit game
    game = pygambit.Game.from_arrays(*lgame)
    result = pygambit.nash.enummixed_solve(game, rational=False)
    return result


def get_recommendation(equilibrium):
    for eq in equilibrium.equilibria:
        stand_probability = eq[equilibrium.game.players[0].strategies[0]]
        hit_probability = eq[equilibrium.game.players[0].strategies[1]]

    recommendation = "Stand" if stand_probability > hit_probability else "Hit"

    # Formulating reasoning
    if recommendation == "Stand":
        reasoning = "Standing has a higher expected value and is statistically safer."
    else:
        reasoning = "Hitting offers a better chance of winning based on Nash equilibrium."

    return {
        "recommendation": recommendation,
        "reasoning": reasoning,
        "hit_probability": round(hit_probability, 3),
        "stand_probability": round(stand_probability, 3)
    }

    
    
@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    player_sum = data.get('player_sum', 0)
    dealer_sum = data.get('dealer_sum', 0)
    has_ace=data.get('has_ace',False)
    
    
    # Basic recommendations for special cases
    if player_sum == 21:
        return jsonify({
            "recommendation": "stand",
            "reasoning": "You have 21! Always stand with 21.",
            "hit_probability": 0.0,
            "stand_probability": 1.0
        })
    
    if player_sum > 21:
        return jsonify({
            "recommendation": "bust",
            "reasoning": "You have busted with a sum over 21.",
            "hit_probability": 0.0,
            "stand_probability": 0.0
        })
    
    # Create game theory model
    ev_stand,ev_hit = simulate_blackjack(player_sum, dealer_sum)
    
    # Find Nash equilibrium
    equilibrium= compute_nash_equilibrium(ev_stand, ev_hit)
    # Check for soft hands (hands with an Ace counted as 11)
    is_soft_hand = has_ace and player_sum <= 21
    
    # Default to basic strategy if game theory fails

        # Get basic strategy recommendation
    if is_soft_hand:
        recommendation, reasoning = recommend_for_soft_hand(player_sum, dealer_sum)
    else:
        recommendation, reasoning = recommend_for_hard_hand(player_sum, dealer_sum)
    
    recommendation_data3= {
        "recommendation": recommendation,
        "reasoning": reasoning ,
        "hit_probability": 1.0 if recommendation == "Hit" else 0.0,
        "stand_probability": 1.0 if recommendation == "Stand" else 0.0
    }
    
    recommendation_data1 = get_recommendation(equilibrium)
    return jsonify({"mixed":recommendation_data1,"normal":recommendation_data3})

def card_value(card):
    """Convert card to numerical value for decision making"""
    if card in ["10", "J", "Q", "K"]:
        return 10
    elif card == "A":
        return 11
    else:
        return int(card)

def recommend_for_hard_hand(player_sum, dealer_value):
    """Provide recommendation for hard hands (no ace counted as 11)"""
    # Always stand on 17 or higher
    if player_sum >= 17:
        return "Stand", f"You have {player_sum}. Basic strategy recommends standing on 17 or higher."
    
    # Always hit on 8 or lower
    if player_sum <= 8:
        return "Hit", f"You have {player_sum}. Basic strategy recommends hitting on 8 or lower."
    
    # For 9, hit unless dealer shows 3-6
    if player_sum == 9:
        if 3 <= dealer_value <= 6:
            return "Hit", f"You have 9 against dealer's {dealer_value}. Consider doubling down, but hit is recommended."
        else:
            return "Hit", f"You have 9 against dealer's {dealer_value}. Basic strategy recommends hitting."
    
    # For 10 or 11, consider doubling down but recommend hit
    if player_sum in [10, 11]:
        return "Hit", f"You have {player_sum} against dealer's {dealer_value}. Ideally double down, but hit is recommended here."
    
    # For 12, hit unless dealer shows 4-6
    if player_sum == 12:
        if 4 <= dealer_value <= 6:
            return "Stand", f"You have 12 against dealer's {dealer_value}. Basic strategy recommends standing."
        else:
            return "Hit", f"You have 12 against dealer's {dealer_value}. Basic strategy recommends hitting."
    
    # For 13-16, stand if dealer shows 2-6, otherwise hit
    if 13 <= player_sum <= 16:
        if 2 <= dealer_value <= 6:
            return "Stand", f"You have {player_sum} against dealer's {dealer_value}. Basic strategy recommends standing."
        else:
            return "Hit", f"You have {player_sum} against dealer's {dealer_value}. Basic strategy recommends hitting."

def recommend_for_soft_hand(player_sum, dealer_value):
    """Provide recommendation for soft hands (with ace counted as 11)"""
    # Special handling for Soft 17 or less
    if player_sum <= 17:
        if 3 <= dealer_value <= 6:
            return "Hit", f"You have soft {player_sum} against dealer's {dealer_value}. Consider doubling down, but hit is recommended."
        else:
            return "Hit", f"You have soft {player_sum} against dealer's {dealer_value}. Basic strategy recommends hitting."
    
    # Soft 18
    if player_sum == 18:
        if dealer_value in [2, 7, 8]:
            return "Stand", f"You have soft 18 against dealer's {dealer_value}. Basic strategy recommends standing."
        elif 3 <= dealer_value <= 6:
            return "Hit", f"You have soft 18 against dealer's {dealer_value}. Consider doubling down, but hit is recommended."
        else:
            return "Hit", f"You have soft 18 against dealer's {dealer_value}. Basic strategy recommends hitting."
    
    # Soft 19 or higher - always stand
    return "Stand", f"You have soft {player_sum}. Basic strategy recommends standing on soft 19 or higher."

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)