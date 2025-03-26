from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import pygambit
import random

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
deck = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]

# Create game theory models for different blackjack scenarios
def simulate_blackjack(player_total, dealer_upcard,can_double_down, num_simulations=100000):
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

        elif player_action == "DoubleDown":
            player_hand += random.choice(deck)  # Player gets one more card
            if player_hand > 21:
                return -2  # Lose twice if busting
            elif dealer_hand == -1 or player_hand > dealer_hand:
                return 2  # Win twice if better than dealer
            elif player_hand == dealer_hand:
                return 0  # Push
            else:
                return -2  # Lose twice
        
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
    if can_double_down:
        results["DoubleDown"] = []  # Add only if Double Down is allowed

    
    for _ in range(num_simulations):
        results["Stand"].append(simulate_hand("Stand"))
        results["Hit"].append(simulate_hand("Hit"))
        if can_double_down:
            results["DoubleDown"].append(simulate_hand("DoubleDown"))


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
    
    def calculate_ev_double(results):
        """ Computes the probabilities and EV from simulation results. """
        single_wins = results.count(1)
        double_wins = results.count(2)
        single_losses = results.count(-1)
        double_losses = results.count(-2)
        pushes = results.count(0)
        total = len(results)
        
        # Calculate effective win/loss probability accounting for double stakes
        win_value = single_wins + (2 * double_wins)
        loss_value = single_losses + (2 * double_losses)
        
        win_prob = single_wins / total
        loss_prob = single_losses / total
        double_win_prob = double_wins / total
        double_loss_prob = double_losses / total
        push_prob = pushes / total
        
        # EV calculation accounting for double stakes
        ev = (win_prob + 2*double_win_prob) - (loss_prob + 2*double_loss_prob)
        
        return win_prob + double_win_prob, loss_prob + double_loss_prob, push_prob, ev

    stand_win, stand_loss, stand_push, ev_stand = calculate_ev(results["Stand"])
    hit_win, hit_loss, hit_push, ev_hit = calculate_ev(results["Hit"])
    if can_double_down:
        double_down_win, double_down_loss, double_down_push, ev_double_down = calculate_ev_double(results["DoubleDown"])
    else:
        double_down_win, double_down_loss, double_down_push, ev_double_down = 0, 0, 0, float('-inf')  # If not allowed, set EV to a very low value


    return ev_stand, ev_hit,ev_double_down

def compute_nash_equilibrium(ev_stand, ev_hit,ev_double_down,can_double_down):
    """ Compute Nash Equilibrium for the player's Hit/Stand decision. """
    
    max_ev = max(ev_stand, ev_hit, ev_double_down)
    if max_ev > 0:
        ev_stand /= max_ev
        ev_hit /= max_ev
        if(can_double_down):
            ev_double_down /= max_ev
    
    player_payoffs = [
        [ev_stand, ev_stand],  # Player chooses Stand
        [ev_hit, ev_hit]  # Player chooses Hit
    ]
    
    dealer_payoffs = [
        [-ev_stand, -ev_stand],  # Dealer loses what Player gains
        [-ev_hit, -ev_hit]  # Dealer loses what Player gains
    ]

    # Include Double Down only if allowed
    if can_double_down:
        player_payoffs.append([ev_double_down, ev_double_down])  # Player chooses Double Down
        dealer_payoffs.append([-ev_double_down, -ev_double_down])  # Dealer loses what Player gains
       
    lgame = (player_payoffs, dealer_payoffs)
    

    # Convert the matrix to a Gambit game
    game = pygambit.Game.from_arrays(*lgame)
    result = pygambit.nash.enummixed_solve(game, rational=False)
    return result


def get_recommendation(equilibrium,can_double_down):
    for eq in equilibrium.equilibria:
        stand_probability = eq[equilibrium.game.players[0].strategies[0]]
        hit_probability = eq[equilibrium.game.players[0].strategies[1]]
        if(can_double_down):
            double_down_probability=eq[equilibrium.game.players[0].strategies[2]]

    strategy_probabilities = {
        "Stand": stand_probability,
        "Hit": hit_probability,
    }
    if can_double_down:
        strategy_probabilities["Double Down"]=double_down_probability
    
    recommendation = max(strategy_probabilities, key=strategy_probabilities.get)

    # Formulating reasoning
    if recommendation == "Stand":
        reasoning = "Standing has the highest expected value and is statistically safer."
    elif recommendation == "Hit":
        reasoning = "Hitting offers a better chance of winning based on Nash equilibrium."
    else:
        reasoning = "Double Down is recommended as it provides the best expected value."

    returns={"recommendation": recommendation,
        "reasoning": reasoning,
        "hit_probability": round(hit_probability, 3),
        "stand_probability": round(stand_probability, 3)}
    if(can_double_down):
        returns["double_down_probability"]=round(double_down_probability, 3)
    return returns
    
@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    player_sum = data.get('player_sum', 0)
    dealer_sum = data.get('dealer_sum', 0)
    has_ace=data.get('has_ace',False)
    can_double_down=data.get('can_double_down',False)
    
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
    ev_stand,ev_hit,ev_double_down = simulate_blackjack(player_sum, dealer_sum,can_double_down)
    
    # Find Nash equilibrium
    equilibrium= compute_nash_equilibrium(ev_stand, ev_hit,ev_double_down,can_double_down)
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
    
    recommendation_data1 = get_recommendation(equilibrium,can_double_down)
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
            return "Double Down", f"You have 9 against dealer's {dealer_value}. Consider doubling down."
        else:
            return "Hit", f"You have 9 against dealer's {dealer_value}. Basic strategy recommends hitting."
    
    # For 10 or 11, consider doubling down but recommend hit
    if player_sum in [10, 11]:
        return "Double Down", f"You have {player_sum} against dealer's {dealer_value}. Ideally double down"
    
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
            return "Double Down", f"You have soft {player_sum} against dealer's {dealer_value}. Consider doubling down."
        else:
            return "Hit", f"You have soft {player_sum} against dealer's {dealer_value}. Basic strategy recommends hitting."
    
    # Soft 18
    if player_sum == 18:
        if dealer_value in [2, 7, 8]:
            return "Stand", f"You have soft 18 against dealer's {dealer_value}. Basic strategy recommends standing."
        elif 3 <= dealer_value <= 6:
            return "Double Down", f"You have soft 18 against dealer's {dealer_value}. Consider doubling down."
        else:
            return "Hit", f"You have soft 18 against dealer's {dealer_value}. Basic strategy recommends hitting."
    
    # Soft 19 or higher - always stand
    return "Stand", f"You have soft {player_sum}. Basic strategy recommends standing on soft 19 or higher."

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)