import socket
import threading
import random
from collections import Counter
from itertools import combinations

# -----------------------------
# Card and Deck
# -----------------------------

suits = ["♠", "♥", "♦", "♣"]
ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
rank_values = {r: i for i, r in enumerate(ranks, start=2)}
value_to_rank = {v: r for r, v in rank_values.items()}

HAND_NAMES = {
    8: "Straight Flush",
    7: "Four of a Kind",
    6: "Full House",
    5: "Flush",
    4: "Straight",
    3: "Three of a Kind",
    2: "Two Pair",
    1: "One Pair",
    0: "High Card",
}

SMALL_BLIND = 5
BIG_BLIND = 10

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.value = rank_values[rank]

    def __repr__(self):
        return f"{self.rank}{self.suit}"

class Deck:
    def __init__(self):
        self.cards = [Card(r, s) for r in ranks for s in suits]
        random.shuffle(self.cards)

    def deal(self, n=1):
        return [self.cards.pop() for _ in range(n)]

# -----------------------------
# Hand evaluation
# -----------------------------

def evaluate_hand(cards):
    values = sorted([c.value for c in cards], reverse=True)
    suits_list = [c.suit for c in cards]
    ranks_list = [c.rank for c in cards]

    counts = Counter(ranks_list)
    most_common = counts.most_common()

    is_flush = len(set(suits_list)) == 1

    uniq_vals = sorted(set(values))
    is_straight = len(uniq_vals) == 5 and uniq_vals[-1] - uniq_vals[0] == 4

    if is_flush and is_straight:
        return (8, values)
    if most_common[0][1] == 4:
        return (7, values)
    if most_common[0][1] == 3 and most_common[1][1] == 2:
        return (6, values)
    if is_flush:
        return (5, values)
    if is_straight:
        return (4, values)
    if most_common[0][1] == 3:
        return (3, values)
    if most_common[0][1] == 2 and most_common[1][1] == 2:
        return (2, values)
    if most_common[0][1] == 2:
        return (1, values)
    return (0, values)

def best_five_of_seven(cards):
    best = (-1, [])
    for combo in combinations(cards, 5):
        score = evaluate_hand(combo)
        if score > best:
            best = score
    return best

def hand_description(score):
    rank_score, values = score
    name = HAND_NAMES.get(rank_score, "Unknown")
    high_val = values[0]
    high_rank = value_to_rank.get(high_val, "?")
    if rank_score == 0:
        return f"{name} ({high_rank} high)"
    return f"{name}, high card {high_rank}"

# -----------------------------
# Simple line-based protocol
# -----------------------------

def send_line(conn, msg: str):
    if not msg.endswith("\n"):
        msg += "\n"
    conn.sendall(msg.encode("utf-8"))

def recv_line(conn) -> str:
    data = b""
    while True:
        chunk = conn.recv(1)
        if not chunk:
            raise ConnectionError("Connection closed by client.")
        if chunk == b"\n":
            break
        data += chunk
    return data.decode("utf-8").strip()

# -----------------------------
# Player I/O abstraction
# -----------------------------

def local_input(prompt: str) -> str:
    return input(prompt)

def remote_input(conn, prompt: str) -> str:
    # Send prompt, wait for reply
    send_line(conn, f"PROMPT:{prompt}")
    response = recv_line(conn)
    # Client should send "ACTION:xxx"
    if response.startswith("ACTION:"):
        return response[len("ACTION:"):].strip()
    return response.strip()

def remote_message(conn, msg: str):
    send_line(conn, f"MSG:{msg}")

# -----------------------------
# Betting round
# -----------------------------

def betting_round(
    p1_chips, p2_chips, pot, stage,
    current_bet=0, p1_contrib=0, p2_contrib=0,
    raise_used=False,
    p1_input_func=None,
    p2_input_func=None,
    p1_message_func=None,
    p2_message_func=None,
):
    print(f"\n--- {stage.upper()} BETTING ROUND ---")
    if p1_message_func:
        p1_message_func(f"--- {stage.upper()} BETTING ROUND ---")
    if p2_message_func:
        p2_message_func(f"--- {stage.upper()} BETTING ROUND ---")

    p1_in = True
    p2_in = True
    p1_all_in = (p1_chips == 0)
    p2_all_in = (p2_chips == 0)
    last_raiser = None

    while True:
        state_line = (
            f"Pot: {pot} | P1 chips: {p1_chips} | P2 chips: {p2_chips} | "
            f"Current bet: {current_bet}"
        )
        print("\n" + state_line)
        if p1_message_func:
            p1_message_func(state_line)
        if p2_message_func:
            p2_message_func(state_line)

        # Early break if someone is all-in and contributions equal
        if (p1_all_in or p2_all_in) and p1_contrib == p2_contrib:
            break

        # -------------------------
        # PLAYER 1 TURN (host)
        # -------------------------
        if p1_in and not p1_all_in:
            to_call = current_bet - p1_contrib

            if to_call > 0:
                if raise_used or p1_chips <= to_call:
                    prompt = "P1: call / fold (or 'all-in' to call if enough): "
                else:
                    prompt = "P1: call / raise / fold (or 'all-in'): "
            else:
                if raise_used:
                    prompt = "P1: check / fold (or 'all-in'): "
                else:
                    prompt = "P1: check / bet / fold (or 'all-in'): "

            action = p1_input_func(prompt).lower()

            if action == "fold":
                print("P1 folds.")
                if p1_message_func:
                    p1_message_func("You fold.")
                if p2_message_func:
                    p2_message_func("Opponent folds.")
                return pot, p1_chips, p2_chips, False, p2_in

            elif action == "all-in":
                bet_amt = p1_chips
                p1_chips -= bet_amt
                p1_contrib += bet_amt
                pot += bet_amt
                print(f"P1 goes all-in for {bet_amt}.")
                if p1_message_func:
                    p1_message_func(f"You go all-in for {bet_amt}.")
                if p2_message_func:
                    p2_message_func(f"Opponent goes all-in for {bet_amt}.")
                if p1_contrib > current_bet:
                    current_bet = p1_contrib
                    last_raiser = "p1"
                    raise_used = True
                p1_all_in = True

            elif action == "call":
                call_amt = min(to_call, p1_chips)
                p1_chips -= call_amt
                p1_contrib += call_amt
                pot += call_amt
                print(f"P1 calls {call_amt}.")
                if p1_message_func:
                    p1_message_func(f"You call {call_amt}.")
                if p2_message_func:
                    p2_message_func(f"Opponent calls {call_amt}.")
                if p1_chips == 0:
                    print("P1 is all-in.")
                    if p1_message_func:
                        p1_message_func("You are all-in.")
                    p1_all_in = True

            elif action == "check":
                if to_call > 0:
                    if p1_message_func:
                        p1_message_func("You cannot check; you must call, all-in, or fold.")
                    print("P1 cannot check; must call/all-in/fold.")
                    continue
                print("P1 checks.")
                if p1_message_func:
                    p1_message_func("You check.")
                if p2_message_func:
                    p2_message_func("Opponent checks.")

            elif action in ("bet", "raise") and not raise_used:
                try:
                    amt_str = p1_input_func("P1: Enter raise amount: ")
                    raise_amt = int(amt_str)
                except:
                    if p1_message_func:
                        p1_message_func("Invalid raise.")
                    print("Invalid raise.")
                    continue

                if raise_amt <= 0 or raise_amt > p1_chips:
                    if p1_message_func:
                        p1_message_func("Invalid raise amount.")
                    print("Invalid raise amount.")
                    continue

                p1_chips -= raise_amt
                p1_contrib += raise_amt
                pot += raise_amt
                current_bet = p1_contrib
                last_raiser = "p1"
                raise_used = True
                print(f"P1 raises to {current_bet}.")
                if p1_message_func:
                    p1_message_func(f"You raise to {current_bet}.")
                if p2_message_func:
                    p2_message_func(f"Opponent raises to {current_bet}.")
                if p1_chips == 0:
                    print("P1 is all-in.")
                    if p1_message_func:
                        p1_message_func("You are all-in.")
                    p1_all_in = True
            else:
                if p1_message_func:
                    p1_message_func("Invalid action.")
                print("Invalid action from P1.")
                continue

        # -------------------------
        # PLAYER 2 TURN (remote)
        # -------------------------
        if p2_in and not p2_all_in:
            to_call = current_bet - p2_contrib

            if to_call > 0:
                if raise_used or p2_chips <= to_call:
                    prompt = "P2: call / fold (or 'all-in' to call if enough): "
                else:
                    prompt = "P2: call / raise / fold (or 'all-in'): "
            else:
                if raise_used:
                    prompt = "P2: check / fold (or 'all-in'): "
                else:
                    prompt = "P2: check / bet / fold (or 'all-in'): "

            action = p2_input_func(prompt).lower()

            if action == "fold":
                print("P2 folds.")
                if p2_message_func:
                    p2_message_func("You fold.")
                if p1_message_func:
                    p1_message_func("Opponent folds.")
                return pot, p1_chips, p2_chips, p1_in, False

            elif action == "all-in":
                bet_amt = p2_chips
                p2_chips -= bet_amt
                p2_contrib += bet_amt
                pot += bet_amt
                print(f"P2 goes all-in for {bet_amt}.")
                if p2_message_func:
                    p2_message_func(f"You go all-in for {bet_amt}.")
                if p1_message_func:
                    p1_message_func(f"Opponent goes all-in for {bet_amt}.")
                if p2_contrib > current_bet:
                    current_bet = p2_contrib
                    last_raiser = "p2"
                    raise_used = True
                p2_all_in = True

            elif action == "call":
                call_amt = min(to_call, p2_chips)
                p2_chips -= call_amt
                p2_contrib += call_amt
                pot += call_amt
                print(f"P2 calls {call_amt}.")
                if p2_message_func:
                    p2_message_func(f"You call {call_amt}.")
                if p1_message_func:
                    p1_message_func(f"Opponent calls {call_amt}.")
                if p2_chips == 0:
                    print("P2 is all-in.")
                    if p2_message_func:
                        p2_message_func("You are all-in.")
                    p2_all_in = True

            elif action == "check":
                if to_call > 0:
                    if p2_message_func:
                        p2_message_func("You cannot check; you must call, all-in, or fold.")
                    print("P2 cannot check; must call/all-in/fold.")
                    continue
                print("P2 checks.")
                if p2_message_func:
                    p2_message_func("You check.")
                if p1_message_func:
                    p1_message_func("Opponent checks.")

            elif action in ("bet", "raise") and not raise_used:
                try:
                    amt_str = p2_input_func("P2: Enter raise amount: ")
                    raise_amt = int(amt_str)
                except:
                    if p2_message_func:
                        p2_message_func("Invalid raise.")
                    print("Invalid raise.")
                    continue

                if raise_amt <= 0 or raise_amt > p2_chips:
                    if p2_message_func:
                        p2_message_func("Invalid raise amount.")
                    print("Invalid raise amount.")
                    continue

                p2_chips -= raise_amt
                p2_contrib += raise_amt
                pot += raise_amt
                current_bet = p2_contrib
                last_raiser = "p2"
                raise_used = True
                print(f"P2 raises to {current_bet}.")
                if p2_message_func:
                    p2_message_func(f"You raise to {current_bet}.")
                if p1_message_func:
                    p1_message_func(f"Opponent raises to {current_bet}.")
                if p2_chips == 0:
                    print("P2 is all-in.")
                    if p2_message_func:
                        p2_message_func("You are all-in.")
                    p2_all_in = True
            else:
                if p2_message_func:
                    p2_message_func("Invalid action.")
                print("Invalid action from P2.")
                continue

        # -------------------------
        # END CONDITION
        # -------------------------
        if p1_contrib == p2_contrib and last_raiser is None:
            break

        if p1_contrib == p2_contrib and last_raiser is not None:
            last_raiser = None

    return pot, p1_chips, p2_chips, p1_in, p2_in

# -----------------------------
# Full game loop (server)
# -----------------------------

def play_full_game(conn):
    player1_chips = 1000  # host
    player2_chips = 1000  # remote
    hand_number = 1

    print("\nWelcome to Texas Hold'em Poker (Heads-Up) - SERVER/PLAYER 1!")
    send_line(conn, "MSG:Welcome to Texas Hold'em Poker (Heads-Up) - You are PLAYER 2.")
    send_line(conn, f"MSG:Small blind: {SMALL_BLIND} | Big blind: {BIG_BLIND}")

    while True:
        print("\n====================================")
        print(f"Hand #{hand_number}")
        print(f"Your chips (P1): {player1_chips} | Opponent chips (P2): {player2_chips}")
        print("====================================")

        send_line(conn, "MSG:====================================")
        send_line(conn, f"MSG:Hand #{hand_number}")
        send_line(conn, f"MSG:Your chips (P2): {player2_chips} | Opponent chips (P1): {player1_chips}")
        send_line(conn, "MSG:====================================")

        if player1_chips <= 0:
            print("\nYou (P1) are out of chips. Player 2 wins the game.")
            send_line(conn, "MSG:Opponent is out of chips. You win the game!")
            break
        if player2_chips <= 0:
            print("\nPlayer 2 is out of chips. You (P1) win the game!")
            send_line(conn, "MSG:You are out of chips. Opponent wins the game.")
            break

        choice = input("Press ENTER to play a hand, or type Q to quit: ").lower()
        if choice == "q":
            print("You quit the game.")
            send_line(conn, "MSG:Host quit the game. Game over.")
            break

        deck = Deck()
        pot = 0

        # Deal hole cards
        p1_cards = deck.deal(2)
        p2_cards = deck.deal(2)

        print("\nYour cards (P1):", p1_cards)
        send_line(conn, f"MSG:Your cards (P2): {p2_cards}")

        # Blinds: P1 = small blind, P2 = big blind
        sb = min(SMALL_BLIND, player1_chips)
        bb = min(BIG_BLIND, player2_chips)

        player1_chips -= sb
        player2_chips -= bb
        pot += sb + bb

        p1_contrib = sb
        p2_contrib = bb
        current_bet = bb

        print(f"\nYou (P1) post small blind: {sb}")
        print(f"Player 2 posts big blind: {bb}")
        print(f"Pot after blinds: {pot}")

        send_line(conn, f"MSG:Opponent posts small blind: {sb}")
        send_line(conn, f"MSG:You post big blind: {bb}")
        send_line(conn, f"MSG:Pot after blinds: {pot}")

        # PRE-FLOP
        pot, player1_chips, player2_chips, p1_in, p2_in = betting_round(
            player1_chips, player2_chips, pot,
            "pre-flop",
            current_bet=current_bet,
            p1_contrib=p1_contrib,
            p2_contrib=p2_contrib,
            raise_used=False,
            p1_input_func=local_input,
            p2_input_func=lambda prompt: remote_input(conn, prompt),
            p1_message_func=lambda msg: print(msg),
            p2_message_func=lambda msg: remote_message(conn, msg),
        )

        if not p1_in:
            player2_chips += pot
            print(f"Player 2 wins the pot of {pot} (you folded pre-flop).")
            send_line(conn, f"MSG:You win the pot of {pot} (opponent folded pre-flop).")
            hand_number += 1
            continue
        if not p2_in:
            player1_chips += pot
            print(f"You win the pot of {pot} (Player 2 folded pre-flop).")
            send_line(conn, f"MSG:Opponent wins the pot of {pot} (you folded pre-flop).")
            hand_number += 1
            continue

        # FLOP
        community = deck.deal(3)
        print("\nFlop:", community)
        send_line(conn, f"MSG:Flop: {community}")

        pot, player1_chips, player2_chips, p1_in, p2_in = betting_round(
            player1_chips, player2_chips, pot,
            "flop",
            p1_input_func=local_input,
            p2_input_func=lambda prompt: remote_input(conn, prompt),
            p1_message_func=lambda msg: print(msg),
            p2_message_func=lambda msg: remote_message(conn, msg),
        )
        if not p1_in:
            player2_chips += pot
            print(f"Player 2 wins the pot of {pot} (you folded on the flop).")
            send_line(conn, f"MSG:You win the pot of {pot} (opponent folded on the flop).")
            hand_number += 1
            continue
        if not p2_in:
            player1_chips += pot
            print(f"You win the pot of {pot} (Player 2 folded on the flop).")
            send_line(conn, f"MSG:Opponent wins the pot of {pot} (you folded on the flop).")
            hand_number += 1
            continue

        # TURN
        community += deck.deal(1)
        print("\nTurn:", community)
        send_line(conn, f"MSG:Turn: {community}")

        pot, player1_chips, player2_chips, p1_in, p2_in = betting_round(
            player1_chips, player2_chips, pot,
            "turn",
            p1_input_func=local_input,
            p2_input_func=lambda prompt: remote_input(conn, prompt),
            p1_message_func=lambda msg: print(msg),
            p2_message_func=lambda msg: remote_message(conn, msg),
        )
        if not p1_in:
            player2_chips += pot
            print(f"Player 2 wins the pot of {pot} (you folded on the turn).")
            send_line(conn, f"MSG:You win the pot of {pot} (opponent folded on the turn).")
            hand_number += 1
            continue
        if not p2_in:
            player1_chips += pot
            print(f"You win the pot of {pot} (Player 2 folded on the turn).")
            send_line(conn, f"MSG:Opponent wins the pot of {pot} (you folded on the turn).")
            hand_number += 1
            continue

        # RIVER
        community += deck.deal(1)
        print("\nRiver:", community)
        send_line(conn, f"MSG:River: {community}")

        pot, player1_chips, player2_chips, p1_in, p2_in = betting_round(
            player1_chips, player2_chips, pot,
            "river",
            p1_input_func=local_input,
            p2_input_func=lambda prompt: remote_input(conn, prompt),
            p1_message_func=lambda msg: print(msg),
            p2_message_func=lambda msg: remote_message(conn, msg),
        )
        if not p1_in:
            player2_chips += pot
            print(f"Player 2 wins the pot of {pot} (you folded on the river).")
            send_line(conn, f"MSG:You win the pot of {pot} (opponent folded on the river).")
            hand_number += 1
            continue
        if not p2_in:
            player1_chips += pot
            print(f"You win the pot of {pot} (Player 2 folded on the river).")
            send_line(conn, f"MSG:Opponent wins the pot of {pot} (you folded on the river).")
            hand_number += 1
            continue

        # SHOWDOWN
        print("\n--- SHOWDOWN ---")
        print("Community cards:", community)
        print("Your cards (P1):", p1_cards)
        print("P2 cards:", p2_cards)

        send_line(conn, "MSG:--- SHOWDOWN ---")
        send_line(conn, f"MSG:Community cards: {community}")
        send_line(conn, f"MSG:Your cards (P2): {p2_cards}")
        send_line(conn, f"MSG:Opponent cards (P1): {p1_cards}")

        p1_best = best_five_of_seven(p1_cards + community)
        p2_best = best_five_of_seven(p2_cards + community)

        print("\nYour hand (P1):", hand_description(p1_best))
        print("P2 hand:", hand_description(p2_best))

        send_line(conn, f"MSG:Your hand: {hand_description(p2_best)}")
        send_line(conn, f"MSG:Opponent hand: {hand_description(p1_best)}")

        if p1_best > p2_best:
            print(f"\nYou win the pot of {pot}!")
            send_line(conn, f"MSG:Opponent wins the pot of {pot}.")
            player1_chips += pot
        elif p2_best > p1_best:
            print(f"\nPlayer 2 wins the pot of {pot}.")
            send_line(conn, f"MSG:You win the pot of {pot}!")
            player2_chips += pot
        else:
            print("\nIt's a tie! Pot is split.")
            send_line(conn, "MSG:It's a tie! Pot is split.")
            player1_chips += pot // 2
            player2_chips += pot // 2

        hand_number += 1

    print("\nThanks for playing!")
    send_line(conn, "MSG:Thanks for playing!")
    send_line(conn, "END:")

def run_server(host="0.0.0.0", port=65432):
    print(f"Starting server on {host}:{port} ...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen(1)
        print("Waiting for a connection...")
        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")
            try:
                play_full_game(conn)
            except ConnectionError as e:
                print(f"Connection lost: {e}")

run_server()