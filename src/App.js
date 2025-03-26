import React, { useState, useEffect, useCallback } from "react";
import "./App.css";

function App() {
  const [gameState, setGameState] = useState({
    playerHand: [],
    dealerHand: [],
    deck: [], // Simulated deck of cards
    gameOver: false,
    message: "", // Game result message (e.g., "You win!", "You lose!")
    dealerHiddenCard: null, // Dealer's hidden card
    balance: 1000, // Player's starting balance
    bet: 10, // Current bet (minimum bet is $10)
    bettingPhase: true, // Whether the game is in the betting phase
  });
  const [recommendation, setRecommendation] = useState(null);

  const {
    playerHand,
    dealerHand,
    gameOver,
    message,
    dealerHiddenCard,
    balance,
    bet,
    bettingPhase,
  } = gameState;

  // Initialize the game

  // Draw a card from the deck
  const drawCard = useCallback((deck) => {
    if (deck.length === 0) return null; // Prevent empty deck errors
    return deck.pop();
  }, []);

  // End the game
  const endGame = useCallback((message, multiplier = 1) => {
    setGameState((prevState) => ({
      ...prevState,
      gameOver: true,
      message,
      balance: prevState.balance + prevState.bet * multiplier,
    }));
  }, []);

  // Calculate the value of a hand
  const calculateHandValue = useCallback((hand) => {
    let value = 0;
    let aceCount = 0;

    hand.forEach((card) => {
      const rank = card.slice(0, -1); // Extract rank, ignoring suit
      if (["J", "Q", "K"].includes(rank)) {
        value += 10;
      } else if (rank === "A") {
        aceCount += 1;
        value += 11;
      } else {
        value += parseInt(rank, 10);
      }
    });

    while (value > 21 && aceCount > 0) {
      value -= 10;
      aceCount -= 1;
    }

    return value;
  }, []);

  // Start a new game
  const startGame = useCallback(() => {
    // Create a deck of cards
    const createDeck = () => {
      const suits = ["♥", "♦", "♠", "♣"];
      const values = [
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "J",
        "Q",
        "K",
        "A",
      ];
      const deck = [];
      for (let suit of suits) {
        for (let value of values) {
          deck.push(`${value}${suit}`);
        }
      }
      return shuffleDeck(deck);
    };

    // Shuffle the deck
    const shuffleDeck = (deck) => {
      for (let i = deck.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [deck[i], deck[j]] = [deck[j], deck[i]];
      }
      return deck;
    };
    const deck = createDeck();
    const playerHand = [drawCard(deck), drawCard(deck)];
    const dealerHand = [drawCard(deck), drawCard(deck)];

    setGameState((prevState) => ({
      ...prevState,
      playerHand,
      dealerHand,
      deck,
      gameOver: false,
      message: "",
      dealerHiddenCard: dealerHand[1],
    }));

    if (calculateHandValue(playerHand) === 21) {
      endGame("Blackjack! You win!", 1.5);
    }
  }, [drawCard, endGame, calculateHandValue]);

  useEffect(() => {
    if (!bettingPhase) {
      startGame();
    }
  }, [bettingPhase, startGame]);

  const getRecommendation = useCallback(
    async (playerHand, dealerHand) => {
      try {
        // Extract card values (remove suits)
        const playerCards = playerHand.map((card) => card.slice(0, -1)); // Remove suit
        const dealerCard = dealerHand.slice(0, -1); // Remove suit

        // Calculate the sum of the player's cards
        const playerSum = calculateHandValue(playerHand);
        // Calculate the sum of the dealer's visible card
        const dealerSum = calculateHandValue([...dealerCard]);
        const has_ace = "A" in playerCards;
        const can_double_down = playerHand.length == 2;
        // Send the data to the backend
        const response = await fetch("http://localhost:5000/recommend", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            player_sum: playerSum, // Sum of player's cards (e.g., 18)
            dealer_sum: dealerSum, // Sum of dealer's visible card (e.g., 10)
            has_ace: has_ace,
            can_double_down: can_double_down,
          }),
        });

        // Parse the response
        const data = await response.json();
        return data;
      } catch (error) {
        console.error("Error fetching recommendation:", error);
        return null;
      }
    },
    [calculateHandValue]
  );

  useEffect(() => {
    async function fetchRecommendation() {
      if (playerHand.length >= 2 && !gameOver) {
        try {
          const response = await getRecommendation(playerHand, dealerHand);
          setRecommendation(response); // Store the recommendation in state
        } catch (error) {
          console.error("Error fetching recommendation:", error);
        }
      }
    }
    fetchRecommendation();
  }, [playerHand, dealerHand, gameOver, getRecommendation]);

  // Player chooses to hit
  const handleHit = async () => {
    setRecommendation(null);
    if (gameOver) return;

    // Draw a new card for the player
    const newPlayerHand = [...playerHand, drawCard(gameState.deck)];
    setGameState((prevState) => ({
      ...prevState,
      playerHand: newPlayerHand,
    }));

    // Check if the player busts
    if (calculateHandValue(newPlayerHand) > 21) {
      endGame("You bust! Dealer wins.", -1);
      setGameState((prevState) => ({
        ...prevState,
        dealerHiddenCard: null, // Reveal the hidden card
      }));
    }
  };

  // Player chooses to stand
  const handleStand = () => {
    setRecommendation(null);
    if (gameOver) return;

    // Reveal the dealer's hidden card
    const newDealerHand = [...dealerHand];
    setGameState((prevState) => ({
      ...prevState,
      dealerHiddenCard: null, // Reveal the hidden card
    }));

    // Dealer draws cards until their hand value is at least 17
    while (calculateHandValue(newDealerHand) < 17) {
      newDealerHand.push(drawCard(gameState.deck));
    }

    setGameState((prevState) => ({
      ...prevState,
      dealerHand: newDealerHand,
    }));

    // Determine the winner
    const playerValue = calculateHandValue(playerHand);
    const dealerValue = calculateHandValue(newDealerHand);

    if (dealerValue > 21) {
      endGame("Dealer busts! You win!", 1);
    } else if (playerValue > dealerValue) {
      endGame("You win!", 1);
    } else if (playerValue < dealerValue) {
      endGame("You lose.", -1);
    } else {
      endGame("It's a tie.", 0);
    }
  };

  const handleDoubleDown = () => {
    setRecommendation(null);
    if (gameOver) return;
    setGameState((prevState) => ({
      ...prevState,
      bet: bet * 2,
    }));
    const newPlayerHand = [...playerHand, drawCard(gameState.deck)];
    setGameState((prevState) => ({
      ...prevState,
      playerHand: newPlayerHand,
    }));
    handleStand();
  };

  // Handle bet placement
  const placeBet = (amount) => {
    if (amount < 10 || amount > balance) {
      alert("Invalid bet amount! Minimum bet is $10.");
      return;
    }
    setGameState((prevState) => ({
      ...prevState,
      bet: amount,
      bettingPhase: false,
    }));
  };

  // Reset the game
  const resetGame = () => {
    setRecommendation(null);
    setGameState((prevState) => ({
      ...prevState,
      playerHand: [],
      dealerHand: [],
      deck: [],
      gameOver: false,
      message: "",
      dealerHiddenCard: null,
      bet: 10, // Reset to minimum bet
      bettingPhase: true,
    }));
  };

  return (
    <div className="App">
      {recommendation && (
        <div className="recommendation-box">
          <p>
            <h1>Mixed Strategy</h1>
            <strong>Recommended Move:</strong>{" "}
            {recommendation.mixed.recommendation}
          </p>
          <p className="reasoning">{recommendation.mixed.reasoning}</p>
        </div>
      )}
      <div className="game">
        {bettingPhase ? (
          <div className="betting">
            <h1>Balance: ${balance}</h1>
            <h2>Place Your Bet</h2>
            <input
              type="range"
              min="10"
              max={balance}
              value={bet}
              onChange={(e) =>
                setGameState((prevState) => ({
                  ...prevState,
                  bet: parseInt(e.target.value),
                }))
              }
            />
            <p>Bet: ${bet}</p>
            <button onClick={() => placeBet(bet)}>Place Bet</button>
          </div>
        ) : (
          <div className="total">
            <div className="play-area">
              <div className="dealer-section">
                <h2>Dealer's Hand</h2>
                <div className="cards">
                  {dealerHand.map((card, index) => (
                    <span key={index} className="card">
                      {index === 1 && dealerHiddenCard ? "??" : card}
                    </span>
                  ))}
                </div>
                <p>
                  Value:{" "}
                  {dealerHiddenCard
                    ? calculateHandValue([dealerHand[0]])
                    : calculateHandValue(dealerHand)}
                </p>
              </div>
              <div className="gap"></div>
              <div className="player-section">
                <p>Bet: ${bet}</p>
                <div className="cards">
                  {playerHand.map((card, index) => (
                    <span key={index} className="card">
                      {card}
                    </span>
                  ))}
                </div>
                <p>Value: {calculateHandValue(playerHand)}</p>
                <div className="balance-bet">
                  <p>Balance: ${balance}</p>
                </div>
                <h2>Your Hand</h2>
              </div>

              {/* Action Buttons with Floating Notification */}
              <div className="buttons">
                <div className="strategies">
                  <div className="button-container">
                    {recommendation?.mixed.recommendation === "Hit" && (
                      <div className="notification">Take this move!</div>
                    )}
                    <button
                      onClick={handleHit}
                      disabled={gameOver}
                      className={
                        recommendation?.mixed.recommendation === "Hit"
                          ? "blinking"
                          : ""
                      }
                    >
                      Hit
                    </button>
                  </div>
                  <div className="button-container">
                    {recommendation?.mixed.recommendation === "Stand" && (
                      <div className="notification">Take this move!</div>
                    )}
                    <button
                      onClick={handleStand}
                      disabled={gameOver}
                      className={
                        recommendation?.mixed.recommendation === "Stand"
                          ? "blinking"
                          : ""
                      }
                    >
                      Stand
                    </button>
                  </div>
                  <div className="button-container">
                    {recommendation?.mixed.recommendation === "Double Down" && (
                      <div className="notification">Take this move!</div>
                    )}
                    <button
                      onClick={handleDoubleDown}
                      disabled={gameOver || playerHand.length > 2}
                      className={
                        recommendation?.mixed.recommendation === "Double Down"
                          ? "blinking"
                          : ""
                      }
                    >
                      Double Down
                    </button>
                  </div>
                </div>
                <button onClick={resetGame}>New Game</button>
              </div>

              {gameOver && <p className="message">{message}</p>}
            </div>
          </div>
        )}
      </div>
      {recommendation && (
        <div className="recommendation-box">
          <p>
            <h1>Normal Strategy</h1>
            <strong>Recommended Move:</strong>{" "}
            {recommendation.normal.recommendation}
          </p>
          <p className="reasoning">{recommendation.normal.reasoning}</p>
        </div>
      )}
    </div>
  );
}

export default App;
