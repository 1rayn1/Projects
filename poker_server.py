import socket
import random
import json
from collections import Counter
from itertools import combinations

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

def send_line(conn, msg: str):
    if not msg.endswith("\n"):
        msg += "\n"
    conn.sendall(msg.encode("utf-8"))

def recv_line(conn) -> str:
    data = b""
    while True:
        chunk = conn.recv(1)
        if not chunk:
            raise ConnectionError("Connection closed.")
        if chunk == b"\n":
            break
        data += chunk
    return data.decode("utf-8").strip()

def local_input(prompt: str) -> str:
    return input(prompt)

def relay_send(sock, to_id, payload: str):
    msg = {"to": to_id, "payload": payload}
    send_line(sock, json.dumps(msg))

def remote_input(sock, to_id, prompt: str) -> str:
    relay_send(sock, to_id, f"PROMPT:{prompt}")
    while True:
        raw = recv_line(sock)
        msg = json.loads(raw)
        payload = msg.get("payload", "")
        if payload.startswith("ACTION:"):
            return payload[len("ACTION:"):].strip()
        # Ignore any other messages (shouldn't happen in this simple setup)

def remote_message(sock, to_id, msg: str):
    relay_send(sock, to_id, f"MSG:{msg}")

def betting_round(
    p1_chips, p2_chips, pot, stage,
    current_bet=0, p1_contrib=0, p2_contrib=0,
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

        if (p1_all_in or p2_all_in) and p1_contrib == p2_contrib:
            break

        if p1_in and not p1_all_in:
            to_call = current_bet - p1_contrib

            if to_call > 0:
                prompt = "P1: call / raise / fold (or 'all-in'): "
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

            elif action in ("bet", "raise"):
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

        if p2_in and not p2_all_in:
            to_call = current_bet - p2_contrib

            if to_call > 0:
                prompt = "P2: call / raise / fold (or 'all-in'): "
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

            elif action in ("bet", "raise"):
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

        if p1_contrib == p2_contrib and last_raiser is None:
            break

        if p1_contrib == p2_contrib and last_raiser is not None:
            last_raiser = None

    return pot, p1_chips, p2_chips, p1_in, p2_in

def play_full_game(sock, my_id, other_id):
    player1_chips = 1000 
    player2_chips = 1000 
    hand_number = 1

    print("\nWelcome to Texas Hold'em Poker (Heads-Up) - HOST/PLAYER 1!")
    relay_send(sock, other_id, "MSG:Welcome to Texas Hold'em Poker (Heads-Up) - You are PLAYER 2.")
    relay_send(sock, other_id, f"MSG:Small blind: {SMALL_BLIND} | Big blind: {BIG_BLIND}")

    while True:
        print("\n====================================")
        print(f"Hand #{hand_number}")
        print(f"Your chips (P1): {player1_chips} | Opponent chips (P2): {player2_chips}")
        print("====================================")

        relay_send(sock, other_id, "MSG:====================================")
        relay_send(sock, other_id, f"MSG:Hand #{hand_number}")
        relay_send(sock, other_id, f"MSG:Your chips (P2): {player2_chips} | Opponent chips (P1): {player1_chips}")
        relay_send(sock, other_id, "MSG:====================================")

        if player1_chips <= 0:
            print("\nYou (P1) are out of chips. Player 2 wins the game.")
            relay_send(sock, other_id, "MSG:Opponent is out of chips. You win the game!")
            break
        if player2_chips <= 0:
            print("\nPlayer 2 is out of chips. You (P1) win the game!")
            relay_send(sock, other_id, "MSG:You are out of chips. Opponent wins the game.")
            break

        choice = input("Press ENTER to play a hand, or type Q to quit: ").lower()
        if choice == "q":
            print("You quit the game.")
            relay_send(sock, other_id, "MSG:Host quit the game. Game over.")
            break

        deck = Deck()
        pot = 0

        p1_cards = deck.deal(2)
        p2_cards = deck.deal(2)

        print("\nYour cards (P1):", p1_cards)
        relay_send(sock, other_id, f"MSG:Your cards (P2): {p2_cards}")

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

        relay_send(sock, other_id, f"MSG:Opponent posts small blind: {sb}")
        relay_send(sock, other_id, f"MSG:You post big blind: {bb}")
        relay_send(sock, other_id, f"MSG:Pot after blinds: {pot}")

        print("\nYour cards (P1):", p1_cards)
        relay_send(sock, other_id, f"MSG:Your cards (P2): {p2_cards}")

        pot, player1_chips, player2_chips, p1_in, p2_in = betting_round(
            player1_chips, player2_chips, pot,
            "pre-flop",
            current_bet=current_bet,
            p1_contrib=p1_contrib,
            p2_contrib=p2_contrib,
            p1_input_func=local_input,
            p2_input_func=lambda prompt: remote_input(sock, other_id, prompt),
            p1_message_func=lambda msg: print(msg),
            p2_message_func=lambda msg: remote_message(sock, other_id, msg),
        )

        if not p1_in:
            player2_chips += pot
            print(f"Player 2 wins the pot of {pot} (you folded pre-flop).")
            relay_send(sock, other_id, f"MSG:You win the pot of {pot} (opponent folded pre-flop).")
            hand_number += 1
            continue
        if not p2_in:
            player1_chips += pot
            print(f"You win the pot of {pot} (Player 2 folded pre-flop).")
            relay_send(sock, other_id, f"MSG:Opponent wins the pot of {pot} (you folded pre-flop).")
            hand_number += 1
            continue

        print("\nYour cards (P1):", p1_cards)
        relay_send(sock, other_id, f"MSG:Your cards (P2): {p2_cards}")

        community = deck.deal(3)
        print("\nFlop:", community)
        relay_send(sock, other_id, f"MSG:Flop: {community}")

        pot, player1_chips, player2_chips, p1_in, p2_in = betting_round(
            player1_chips, player2_chips, pot,
            "flop",
            p1_input_func=local_input,
            p2_input_func=lambda prompt: remote_input(sock, other_id, prompt),
            p1_message_func=lambda msg: print(msg),
            p2_message_func=lambda msg: remote_message(sock, other_id, msg),
        )
        if not p1_in:
            player2_chips += pot
            print(f"Player 2 wins the pot of {pot} (you folded on the flop).")
            relay_send(sock, other_id, f"MSG:You win the pot of {pot} (opponent folded on the flop).")
            hand_number += 1
            continue
        if not p2_in:
            player1_chips += pot
            print(f"You win the pot of {pot} (Player 2 folded on the flop).")
            relay_send(sock, other_id, f"MSG:Opponent wins the pot of {pot} (you folded on the flop).")
            hand_number += 1
            continue

        print("\nYour cards (P1):", p1_cards)
        relay_send(sock, other_id, f"MSG:Your cards (P2): {p2_cards}")

        community += deck.deal(1)
        print("\nTurn:", community)
        relay_send(sock, other_id, f"MSG:Turn: {community}")

        pot, player1_chips, player2_chips, p1_in, p2_in = betting_round(
            player1_chips, player2_chips, pot,
            "turn",
            p1_input_func=local_input,
            p2_input_func=lambda prompt: remote_input(sock, other_id, prompt),
            p1_message_func=lambda msg: print(msg),
            p2_message_func=lambda msg: remote_message(sock, other_id, msg),
        )
        if not p1_in:
            player2_chips += pot
            print(f"Player 2 wins the pot of {pot} (you folded on the turn).")
            relay_send(sock, other_id, f"MSG:You win the pot of {pot} (opponent folded on the turn).")
            hand_number += 1
            continue
        if not p2_in:
            player1_chips += pot
            print(f"You win the pot of {pot} (Player 2 folded on the turn).")
            relay_send(sock, other_id, f"MSG:Opponent wins the pot of {pot} (you folded on the turn).")
            hand_number += 1
            continue

        print("\nYour cards (P1):", p1_cards)
        relay_send(sock, other_id, f"MSG:Your cards (P2): {p2_cards}")

        community += deck.deal(1)
        print("\nRiver:", community)
        relay_send(sock, other_id, f"MSG:River: {community}")

        pot, player1_chips, player2_chips, p1_in, p2_in = betting_round(
            player1_chips, player2_chips, pot,
            "river",
            p1_input_func=local_input,
            p2_input_func=lambda prompt: remote_input(sock, other_id, prompt),
            p1_message_func=lambda msg: print(msg),
            p2_message_func=lambda msg: remote_message(sock, other_id, msg),
        )
        if not p1_in:
            player2_chips += pot
            print(f"Player 2 wins the pot of {pot} (you folded on the river).")
            relay_send(sock, other_id, f"MSG:You win the pot of {pot} (opponent folded on the river).")
            hand_number += 1
            continue
        if not p2_in:
            player1_chips += pot
            print(f"You win the pot of {pot} (Player 2 folded on the river).")
            relay_send(sock, other_id, f"MSG:Opponent wins the pot of {pot} (you folded on the river).")
            hand_number += 1
            continue

        print("\n--- SHOWDOWN ---")
        print("Community cards:", community)
        print("Your cards (P1):", p1_cards)
        print("P2 cards:", p2_cards)

        relay_send(sock, other_id, "MSG:--- SHOWDOWN ---")
        relay_send(sock, other_id, f"MSG:Community cards: {community}")
        relay_send(sock, other_id, f"MSG:Your cards (P2): {p2_cards}")
        relay_send(sock, other_id, f"MSG:Opponent cards (P1): {p1_cards}")

        p1_best = best_five_of_seven(p1_cards + community)
        p2_best = best_five_of_seven(p2_cards + community)

        print("\nYour hand (P1):", hand_description(p1_best))
        print("P2 hand:", hand_description(p2_best))

        relay_send(sock, other_id, f"MSG:Your hand: {hand_description(p2_best)}")
        relay_send(sock, other_id, f"MSG:Opponent hand: {hand_description(p1_best)}")

        if p1_best > p2_best:
            print(f"\nYou win the pot of {pot}!")
            relay_send(sock, other_id, f"MSG:Opponent wins the pot of {pot}.")
            player1_chips += pot
        elif p2_best > p1_best:
            print(f"\nPlayer 2 wins the pot of {pot}.")
            relay_send(sock, other_id, f"MSG:You win the pot of {pot}!")
            player2_chips += pot
        else:
            print("\nIt's a tie! Pot is split.")
            relay_send(sock, other_id, "MSG:It's a tie! Pot is split.")
            player1_chips += pot // 2
            player2_chips += pot // 2

        hand_number += 1

    print("\nThanks for playing!")
    relay_send(sock, other_id, "MSG:Thanks for playing!")
    relay_send(sock, other_id, "END:")

def connect_to_relay(host="127.0.0.1", port=9000):
    print(f"Connecting to relay at {host}:{port} ...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        print("Connected to relay.")

        welcome_raw = recv_line(s)
        welcome = json.loads(welcome_raw)
        my_id = welcome["id"]
        print(f"My relay ID (HOST / P1): {my_id}")

        other_id = input("Enter opponent's relay ID (P2): ").strip()

        try:
            play_full_game(s, my_id, other_id)
        except ConnectionError as e:
            print(f"Connection lost: {e}")


relay_ip = input("Relay IP (default 127.0.0.1): ").strip() or "127.0.0.1"
relay_port_str = input("Relay port (default 9000): ").strip() or "9000"
relay_port = int(relay_port_str)
connect_to_relay(relay_ip, relay_port)