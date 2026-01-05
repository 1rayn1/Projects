import random
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


def estimate_cpu_strength(cpu_cards, community):
    total = cpu_cards + community
    if len(total) >= 5:
        rank_score, values = best_five_of_seven(total)
        rank_norm = rank_score / 8.0
        high_norm = values[0] / 14.0
        strength = 0.6 * rank_norm + 0.4 * high_norm
    else:
        values = [c.value for c in total]
        strength = max(values) / 14.0
    return max(0.0, min(1.0, strength))


def betting_round(player_chips, cpu_chips, pot, stage,
                  cpu_strength,
                  current_bet=0, player_contrib=0, cpu_contrib=0,
                  raise_used=False):
    print(f"\n--- {stage.upper()} BETTING ROUND ---")

    player_in = True
    cpu_in = True
    player_all_in = (player_chips == 0)
    cpu_all_in = (cpu_chips == 0)
    last_raiser = None

    while True:
        print(f"\nPot: {pot}")
        print(f"Your chips: {player_chips} | CPU chips: {cpu_chips}")
        print(f"Current bet: {current_bet}")

        # Early break if someone is all-in and contributions equal
        if (player_all_in or cpu_all_in) and player_contrib == cpu_contrib:
            break

        # -------------------------
        # PLAYER TURN
        # -------------------------
        if player_in and not player_all_in:
            to_call = current_bet - player_contrib

            if to_call > 0:
                if raise_used or player_chips <= to_call:
                    action = input("match / fold (or 'all-in' to match if enough): ").lower()
                else:
                    action = input("match / raise / fold (or 'all-in'): ").lower()
            else:
                if raise_used:
                    action = input("check / fold (or 'all-in'): ").lower()
                else:
                    action = input("check / bet / fold (or 'all-in'): ").lower()

            if action == "fold" or action == "f":
                print("You fold.")
                return pot, player_chips, cpu_chips, False, cpu_in

            elif action == "all-in" or action == "a":
                bet_amt = player_chips
                player_chips -= bet_amt
                player_contrib += bet_amt
                pot += bet_amt
                print(f"You go all-in for {bet_amt}.")
                if player_contrib > current_bet:
                    current_bet = player_contrib
                    last_raiser = "player"
                    raise_used = True
                player_all_in = True

            elif action == "match" or action == "m":
                call_amt = min(to_call, player_chips)
                player_chips -= call_amt
                player_contrib += call_amt
                pot += call_amt
                print(f"You call {call_amt}.")
                if player_chips == 0:
                    print("You are all-in.")
                    player_all_in = True

            elif action == "check" or action == "c":
                if to_call > 0:
                    print("You cannot check; you must match, all-in, or fold.")
                    continue
                print("You check.")

            elif action in ("bet", "raise","b","r") and not raise_used:
                try:
                    raise_amt = int(input("Enter raise amount: "))
                except:
                    print("Invalid raise.")
                    continue

                if raise_amt <= 0 or raise_amt > player_chips:
                    print("Invalid raise amount.")
                    continue

                player_chips -= raise_amt
                player_contrib += raise_amt
                pot += raise_amt
                current_bet = player_contrib
                last_raiser = "player"
                raise_used = True
                print(f"You raise to {current_bet}.")
                if player_chips == 0:
                    print("You are all-in.")
                    player_all_in = True
            else:
                print("Invalid action.")
                continue

        # -------------------------
        # CPU TURN
        # -------------------------
        if cpu_in and not cpu_all_in:
            to_call = current_bet - cpu_contrib

            # CPU action selection using strength + constraints
            if to_call > 0:
                if cpu_chips <= to_call:
                    # Only call (all-in) or fold
                    if cpu_strength > 0.25:
                        cpu_action = "match"
                    else:
                        cpu_action = random.choice(["match", "fold"])
                else:
                    if raise_used:
                        # Can only match or fold
                        if cpu_strength > 0.6:
                            cpu_action = "match"
                        elif cpu_strength < 0.3:
                            cpu_action = "fold"
                        else:
                            cpu_action = random.choice(["match", "fold"])
                    else:
                        # Can raise
                        if cpu_strength > 0.8:
                            cpu_action = "raise"
                        elif cpu_strength > 0.5:
                            cpu_action = random.choice(["match", "raise"])
                        elif cpu_strength < 0.3:
                            cpu_action = random.choice(["match", "fold"])
                        else:
                            cpu_action = "match"
            else:
                if cpu_chips == 0:
                    cpu_action = "check"
                else:
                    if raise_used:
                        if cpu_strength > 0.5:
                            cpu_action = "check"
                        else:
                            cpu_action = "check"
                    else:
                        if cpu_strength > 0.8:
                            cpu_action = "raise"
                        elif cpu_strength > 0.5:
                            cpu_action = random.choice(["check", "raise"])
                        else:
                            cpu_action = "check"

            if cpu_action == "fold":
                print("CPU folds.")
                return pot, player_chips, cpu_chips, player_in, False

            elif cpu_action == "match":
                call_amt = min(to_call, cpu_chips)
                cpu_chips -= call_amt
                cpu_contrib += call_amt
                pot += call_amt
                print(f"CPU matches {call_amt}.")
                if cpu_chips == 0:
                    print("CPU is all-in.")
                    cpu_all_in = True

            elif cpu_action == "check":
                print("CPU checks.")

            elif cpu_action == "raise" and not raise_used:
                raise_amt = min(20, cpu_chips)
                if raise_amt <= 0:
                    print("CPU checks.")
                else:
                    cpu_chips -= raise_amt
                    cpu_contrib += raise_amt
                    pot += raise_amt
                    current_bet = cpu_contrib
                    last_raiser = "cpu"
                    raise_used = True
                    print(f"CPU raises to {current_bet}.")
                    if cpu_chips == 0:
                        print("CPU is all-in.")
                        cpu_all_in = True

        if player_contrib == cpu_contrib and last_raiser is None:
            break

        if player_contrib == cpu_contrib and last_raiser is not None:
            last_raiser = None

    return pot, player_chips, cpu_chips, player_in, cpu_in



player_chips = 1000
cpu_chips = 1000
hand_number = 1

print("\nWelcome to Texas Hold'em Poker (Heads-Up)!")
print("Small blind:", SMALL_BLIND, "| Big blind:", BIG_BLIND)
print("Game continues until someone reaches $0 or you quit.\n")

while True:
    print("\n====================================")
    print(f"Hand #{hand_number}")
    print(f"Your chips: {player_chips} | CPU chips: {cpu_chips}")
    print("====================================")

    if player_chips <= 0:
        print("\nYou are out of chips. CPU wins the game.")
        break
    if cpu_chips <= 0:
        print("\nCPU is out of chips. You win the game!")
        break

    choice = input("Press ENTER to play a hand, or type Q to quit: ").lower()
    if choice == "q":
        print("You quit the game.")
        break

    deck = Deck()
    pot = 0

    player = deck.deal(2)
    cpu = deck.deal(2)

    print("\nYour cards:", player)

    # Blinds: player = small blind, CPU = big blind
    sb = min(SMALL_BLIND, player_chips)
    bb = min(BIG_BLIND, cpu_chips)

    player_chips -= sb
    cpu_chips -= bb
    pot += sb + bb

    player_contrib = sb
    cpu_contrib = bb
    current_bet = bb

    print(f"\nYou post small blind: {sb}")
    print(f"CPU posts big blind: {bb}")
    print(f"Pot after blinds: {pot}")

    print("\nYour cards:", player)

    # PRE-FLOP
    cpu_strength = estimate_cpu_strength(cpu, [])
    pot, player_chips, cpu_chips, p_in, c_in = betting_round(
        player_chips, cpu_chips, pot,
        "pre-flop",
        cpu_strength,
        current_bet=current_bet,
        player_contrib=player_contrib,
        cpu_contrib=cpu_contrib,
        raise_used=False
    )

    if not p_in:
        cpu_chips += pot
        print(f"CPU wins the pot of {pot} (you folded pre-flop).")
        hand_number += 1
        continue
    if not c_in:
        player_chips += pot
        print(f"You win the pot of {pot} (CPU folded pre-flop).")
        hand_number += 1
        continue

    print("\nYour cards:", player)

    # FLOP
    community = deck.deal(3)
    print("\nFlop:", community)

    cpu_strength = estimate_cpu_strength(cpu, community)
    pot, player_chips, cpu_chips, p_in, c_in = betting_round(
        player_chips, cpu_chips, pot,
        "flop",
        cpu_strength
    )
    if not p_in:
        cpu_chips += pot
        print(f"CPU wins the pot of {pot} (you folded on the flop).")
        hand_number += 1
        continue
    if not c_in:
        player_chips += pot
        print(f"You win the pot of {pot} (CPU folded on the flop).")
        hand_number += 1
        continue


    print("\nYour cards:", player)

    # TURN
    community += deck.deal(1)
    print("\nTurn:", community)

    cpu_strength = estimate_cpu_strength(cpu, community)
    pot, player_chips, cpu_chips, p_in, c_in = betting_round(
        player_chips, cpu_chips, pot,
        "turn",
        cpu_strength
    )
    if not p_in:
        cpu_chips += pot
        print(f"CPU wins the pot of {pot} (you folded on the turn).")
        hand_number += 1
        continue
    if not c_in:
        player_chips += pot
        print(f"You win the pot of {pot} (CPU folded on the turn).")
        hand_number += 1
        continue

    print("\nYour cards:", player)

    # RIVER
    community += deck.deal(1)
    print("\nRiver:", community)

    cpu_strength = estimate_cpu_strength(cpu, community)
    pot, player_chips, cpu_chips, p_in, c_in = betting_round(
        player_chips, cpu_chips, pot,
        "river",
        cpu_strength
    )
    if not p_in:
        cpu_chips += pot
        print(f"CPU wins the pot of {pot} (you folded on the river).")
        hand_number += 1
        continue
    if not c_in:
        player_chips += pot
        print(f"You win the pot of {pot} (CPU folded on the river).")
        hand_number += 1
        continue

    # SHOWDOWN
    print("\n--- SHOWDOWN ---")
    print("Community cards:", community)
    print("Your cards:     ", player)
    print("CPU cards:      ", cpu)

    player_best = best_five_of_seven(player + community)
    cpu_best = best_five_of_seven(cpu + community)

    print("\nYour hand:", hand_description(player_best))
    print("CPU hand:", hand_description(cpu_best))

    if player_best > cpu_best:
        print(f"\nYou win the pot of {pot}!")
        player_chips += pot
    elif cpu_best > player_best:
        print(f"\nCPU wins the pot of {pot}.")
        cpu_chips += pot
    else:
        print("\nIt's a tie! Pot is split.")
        player_chips += pot // 2
        cpu_chips += pot // 2

    hand_number += 1

print("\nThanks for playing!")