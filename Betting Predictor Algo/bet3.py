import json
import requests

LIVE_URL = "https://api-h2h.hudstats.com/v1/live/nba"
PARTICIPANT_URL = "https://api-h2h.hudstats.com/v1/participant/nba?limit=15"
PARTICIPANT_OVERRIDES_FILE = "participant_overrides.json"

BET_LOG_FILE = "bet_log.json"
LIVE_CACHE_FILE = "live_cache.json"
PARTICIPANT_CACHE_FILE = "participant_cache.json"
PENDING_BETS_FILE = "pending_bets.json"


# ---------- FILE HELPERS ----------
def load_json_file(filename, default):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json_file(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


def load_bet_log():
    return load_json_file(BET_LOG_FILE, [])


def save_bet_log(log):
    save_json_file(BET_LOG_FILE, log)

def load_pending_bets():
    return load_json_file(PENDING_BETS_FILE, [])


def save_pending_bets(bets):
    save_json_file(PENDING_BETS_FILE, bets)


# ---------- API / CACHE ----------
def fetch_live_games():
    try:
        response = requests.get(LIVE_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        save_json_file(LIVE_CACHE_FILE, data)
        print("✅ Live games pulled from API")
        return data
    except Exception as e:
        print(f"⚠️ Live API failed, using cache: {e}")
        return load_json_file(LIVE_CACHE_FILE, [])


def fetch_participant_stats():
    try:
        response = requests.get(PARTICIPANT_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        save_json_file(PARTICIPANT_CACHE_FILE, data)
        print("✅ Participant stats pulled from API")
        return data
    except Exception as e:
        print(f"⚠️ Participant API failed, using cache: {e}")
        return load_json_file(PARTICIPANT_CACHE_FILE, [])
    
def fetch_combined_participant_stats():
    api_stats = fetch_participant_stats()
    override_stats = load_json_file(PARTICIPANT_OVERRIDES_FILE, [])

    combined = list(api_stats)

    existing_names = {
        item.get("participantName", "").strip().upper()
        for item in api_stats
    }

    for item in override_stats:
        name = item.get("participantName", "").strip().upper()
        if name not in existing_names:
            combined.append(item)

    return combined


# ---------- HELPERS ----------
def quarter_clock_to_minutes_played(quarter, clock_str):
    clock_str = clock_str.strip()

    if ":" in clock_str:
        mins, secs = map(int, clock_str.split(":"))
    else:
        mins = int(clock_str)
        secs = 0

    remaining_in_quarter = mins + secs / 60
    return (quarter - 1) * 12 + (12 - remaining_in_quarter)


def form_score(form_list):
    score = 0
    for result in form_list:
        if result == "w":
            score += 1
        elif result == "l":
            score -= 1
    return score


def short_team_name(full_name):
    return full_name.split()[-1]


def build_matchup_name(game):
    team_a = short_team_name(game["teamAName"])
    team_b = short_team_name(game["teamBName"])
    return (
        f"{game['participantAName']}_vs_{game['participantBName']}__"
        f"{team_a}_vs_{team_b}"
    )


def find_participant_stats(participant_name, participant_stats_list):
    for item in participant_stats_list:
        if item.get("participantName", "").strip().upper() == participant_name.strip().upper():
            return item
    return None


# ---------- MODEL ----------
def build_stats_from_participants(game, participant_stats_list):
    a_stats = find_participant_stats(game["participantAName"], participant_stats_list)
    b_stats = find_participant_stats(game["participantBName"], participant_stats_list)

    default_player_avg = 54.8

    a_found = a_stats is not None
    b_found = b_stats is not None

    a_avg = a_stats.get("avgPoints", default_player_avg) if a_stats else default_player_avg
    b_avg = b_stats.get("avgPoints", default_player_avg) if b_stats else default_player_avg

    historical_total = a_avg + b_avg
    historical_pace = historical_total / 48

    form_a = a_stats.get("matchForm", []) if a_stats else []
    form_b = b_stats.get("matchForm", []) if b_stats else []

    return {
        "historical_total": historical_total,
        "historical_pace": historical_pace,
        "form_a": form_a,
        "form_b": form_b,
        "a_avg_points": a_avg,
        "b_avg_points": b_avg,
        "a_found": a_found,
        "b_found": b_found,
    }



def predict_total(current_score, minutes_played, historical_pace):
    minutes_left = 48 - minutes_played
    historical_total = historical_pace * 48

    if minutes_played <= 0:
        return historical_total

    current_pace = current_score / minutes_played
    live_projection = current_score + (current_pace * minutes_left)

    # smooth 1-minute-style scaling
    live_weight = 0.05 + ((48 - minutes_left) / 48) * 0.85
    live_weight = max(0.05, min(live_weight, 0.90))

    hist_weight = 1 - live_weight
    raw_prediction = (live_weight * live_projection) + (hist_weight * historical_total)

    if minutes_left <= 6:
        floor_ppm = 2.8
    elif minutes_left <= 12:
        floor_ppm = 2.4
    else:
        floor_ppm = 2.1

    minimum_reasonable = current_score + (minutes_left * floor_ppm)

    prediction = max(raw_prediction, minimum_reasonable, current_score)
    return prediction


def adjust_prediction(prediction, form_a, form_b, score_diff, minutes_left):
    form_edge = form_score(form_a[:5]) + form_score(form_b[:5])
    prediction += form_edge * 0.4

    if score_diff <= 5 and minutes_left <= 3:
        prediction += 4
    elif score_diff >= 15 and minutes_left <= 6:
        prediction -= 8

    return prediction


# ---------- LEARNING ----------
def get_recommended_thresholds():
    log = load_bet_log()

    over_wins = {}
    over_total = {}
    under_wins = {}
    under_total = {}

    for bet in log:
        side = bet.get("bet_side")
        edge = abs(float(bet.get("edge", 0)))
        result = bet.get("result")

        bucket = int(edge)

        if side == "OVER":
            over_total[bucket] = over_total.get(bucket, 0) + 1
            if result == "WIN":
                over_wins[bucket] = over_wins.get(bucket, 0) + 1

        elif side == "UNDER":
            under_total[bucket] = under_total.get(bucket, 0) + 1
            if result == "WIN":
                under_wins[bucket] = under_wins.get(bucket, 0) + 1

    best_over = 5
    best_under = 5
    best_over_rate = -1
    best_under_rate = -1

    for bucket, total in over_total.items():
        if total >= 3:
            rate = over_wins.get(bucket, 0) / total
            if rate > best_over_rate:
                best_over_rate = rate
                best_over = bucket

    for bucket, total in under_total.items():
        if total >= 3:
            rate = under_wins.get(bucket, 0) / total
            if rate > best_under_rate:
                best_under_rate = rate
                best_under = bucket

    return best_over, best_under


def betting_decision(game, quarter, minutes_played, vegas_line, participant_stats_list, pace_modifier=1.0):
    current_score = game["teamAScore"] + game["teamBScore"]
    score_diff = abs(game["teamAScore"] - game["teamBScore"])

    stats = build_stats_from_participants(game, participant_stats_list)

    historical_pace = stats["historical_pace"]
    historical_total = stats["historical_total"]
    form_a = stats["form_a"]
    form_b = stats["form_b"]
    used_cache_stats = stats["a_found"] and stats["b_found"]

    prediction = predict_total(
        current_score=current_score,
        minutes_played=minutes_played,
        historical_pace=historical_pace
    )

    prediction *= pace_modifier

    minutes_left = 48 - minutes_played

    prediction = adjust_prediction(
        prediction,
        form_a,
        form_b,
        score_diff,
        minutes_left
    )

    # late Q4 under inflation
    if quarter == 4 and minutes_left <= 5:
        prediction += 4

    prediction = vegas_line + (prediction - vegas_line) * 0.72

    prediction = max(prediction, current_score)

    edge = prediction - vegas_line

    over_threshold, under_threshold = get_recommended_thresholds()

    over_threshold = max(over_threshold, 7)
    under_threshold = max(under_threshold, 6)

    if minutes_played < 24:
        over_threshold += 3
        under_threshold += 2
    elif minutes_left >= 12:
        over_threshold += 1
        under_threshold += 1

    if edge >= over_threshold:
        recommendation = "OVER"
        display_recommendation = "🔥 BET OVER"
    elif edge <= -under_threshold:
        recommendation = "UNDER"
        display_recommendation = "❄️ BET UNDER"
    else:
        recommendation = "NO BET"
        display_recommendation = "⏸️ NO BET"

    trigger_buffer = 1.25

    take_over_below = prediction - (over_threshold * trigger_buffer)
    take_under_above = prediction + (under_threshold * trigger_buffer)

    return {
        "recommendation": recommendation,
        "display_recommendation": display_recommendation,
        "prediction": round(prediction, 1),
        "edge": round(edge, 1),
        "historical_total": round(historical_total, 1),
        "current_score": current_score,
        "score_diff": score_diff,
        "over_threshold": over_threshold,
        "under_threshold": under_threshold,
        "used_participant_stats": used_cache_stats,
         "take_over_below": round(take_over_below, 1),
        "take_under_above": round(take_under_above, 1),
    }


# ---------- LOGGING ----------
def save_pending_bet(matchup, bet_side, line, prediction, edge, quarter, clock, current_score, manual_override=False, pace_choice="n"):
    pending_bets = load_pending_bets()

    for bet in pending_bets:
        if (
            bet["matchup"] == matchup and
            bet["bet_side"] == bet_side and
            float(bet["line"]) == float(line)
        ):
            print("⚠️ Matching pending bet already exists.\n")
            return

    entry = {
        "matchup": matchup,
        "bet_side": bet_side,
        "line": line,
        "prediction": prediction,
        "edge": edge,
        "quarter": quarter,
        "clock": clock,
        "current_score": current_score,
        "manual_override": manual_override,
        "pace_choice": pace_choice,
    }

    pending_bets.append(entry)
    save_pending_bets(pending_bets)

    if manual_override:
        print("✅ Manual override pending bet saved.\n")
    else:
        print("✅ Pending bet saved.\n")


def log_bet_result():
    pending_bets = load_pending_bets()

    if not pending_bets:
        print("\nNo pending bets saved yet.\n")
        return

    print("\nPending Bets:")
    for i, bet in enumerate(pending_bets, 1):
        print(
            f"{i}. {bet['matchup']} | "
            f"{bet['bet_side']} | "
            f"Line: {bet['line']} | "
            f"Prediction: {bet['prediction']} | "
            f"Edge: {bet['edge']} | "
            f"Pace: {bet.get('pace_choice', 'n')} | "
            f"Q{bet['quarter']} {bet['clock']}"
        )

    try:
        choice = int(input("\nSelect pending bet number: ").strip())
        if choice < 1 or choice > len(pending_bets):
            print("Invalid selection.\n")
            return
    except ValueError:
        print("Invalid input.\n")
        return

    selected_bet = pending_bets[choice - 1]

    try:
        final_score_a = float(input("Final score Team A: ").strip())
        final_score_b = float(input("Final score Team B: ").strip())
        final_total = final_score_a + final_score_b
    except ValueError:
        print("Invalid final scores.\n")
        return

    pending_bets.pop(choice - 1)

    bet_side = selected_bet["bet_side"]
    line = float(selected_bet["line"])

    if bet_side == "OVER":
        result = "WIN" if final_total > line else "LOSS"
    elif bet_side == "UNDER":
        result = "WIN" if final_total < line else "LOSS"
    else:
        print("Invalid bet side.\n")
        return

    log = load_bet_log()

    completed_entry = {
        "matchup": selected_bet["matchup"],
        "bet_side": bet_side,
        "line": line,
        "prediction": selected_bet["prediction"],
        "edge": selected_bet["edge"],
        "quarter": selected_bet["quarter"],
        "clock": selected_bet["clock"],
        "pace_choice": selected_bet.get("pace_choice", "n"),
        "current_score": selected_bet["current_score"],
        "final_score_a": final_score_a,
        "final_score_b": final_score_b,
        "final_total": final_total,
        "result": result
    }

    log.append(completed_entry)
    save_bet_log(log)
    save_pending_bets(pending_bets)
    print(f"\n Final Score: {final_total}\n")
    print(f"\nSaved bet result: {result}\n")


def show_bet_summary():
    log = load_bet_log()

    if not log:
        print("\nNo bets logged yet.\n")
        return

    wins = sum(1 for x in log if x["result"] == "WIN")
    total = len(log)
    losses = total - wins
    win_pct = (wins / total) * 100 if total else 0

    over_threshold, under_threshold = get_recommended_thresholds()

    over_threshold = min(over_threshold, 9)
    under_threshold = min(under_threshold, 7)

    print("\n----- BET SUMMARY -----")
    print(f"Total Bets: {total}")
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Win %: {win_pct:.1f}%")
    print(f"Recommended OVER threshold: {over_threshold}")
    print(f"Recommended UNDER threshold: {under_threshold}")
    print("-----------------------\n")


# ---------- UI ----------
def show_games(games):
    print("\nLive Games:")
    for i, game in enumerate(games, 1):
        score_a = game["teamAScore"]
        score_b = game["teamBScore"]

        print(
            f"{i}. {game['participantAName']} vs {game['participantBName']} | "
            f"{game['teamAName']} vs {game['teamBName']} | "
            f"{score_a}-{score_b}"
        )
    print()


def live_prediction():
    games = fetch_live_games()
    live_games = [g for g in games if g["status"] == "live"]

    if not live_games:
        print("\nNo live games found.\n")
        return

    participant_stats_list = fetch_combined_participant_stats()

    show_games(live_games)

    choice = int(input("Select game number: "))
    game = live_games[choice - 1]

    quarter = int(input("Quarter (1-4): "))
    clock = input("Clock remaining (mm:ss): ")
    vegas_line = float(input("Live O/U line: "))

    pace_choice = input("Pace? (f = fast, n = normal, s = slow): ").strip().lower()

    if pace_choice == "f":
        pace_modifier = 1.05
    elif pace_choice == "s":
        pace_modifier = 0.98
    else:
        pace_modifier = 1.0

    minutes_played = quarter_clock_to_minutes_played(quarter, clock)
    result = betting_decision(
    game,
    quarter,
    minutes_played,
    vegas_line,
    participant_stats_list,
    pace_modifier
    )
    matchup_name = build_matchup_name(game)

    print("\n----- RESULT -----")
    print("Matchup:", matchup_name)
    print("Historical Total:", result["historical_total"])
    print("Prediction:", result["prediction"])
    print("Edge:", result["edge"])
    print("Take OVER if line drops below:", result["take_over_below"])
    print("Take UNDER if line goes above:", result["take_under_above"])
    print("Current learned OVER threshold:", result["over_threshold"])
    print("Current learned UNDER threshold:", result["under_threshold"])
    print("Used participant stats:", result["used_participant_stats"])
    print(result["display_recommendation"])
    print("------------------\n")

    if result["recommendation"] in ["OVER", "UNDER"]:
        save_pending_bet(
            matchup=matchup_name,
            bet_side=result["recommendation"],
            line=vegas_line,
            prediction=result["prediction"],
            edge=result["edge"],
            quarter=quarter,
            clock=clock,
            current_score=result["current_score"],
            manual_override=False,
            pace_choice=pace_choice
        )
    else:
        take_anyway = input("No bet. Do you still want to save a manual bet? (y/n): ").strip().lower()
        if take_anyway == "y":
            manual_side = input("Enter side to take (OVER/UNDER): ").strip().upper()

            if manual_side not in ["OVER", "UNDER"]:
                print("Invalid side. Manual bet not saved.\n")
            else:
                save_pending_bet(
                    matchup=matchup_name,
                    bet_side=manual_side,
                    line=vegas_line,
                    prediction=result["prediction"],
                    edge=result["edge"],
                    quarter=quarter,
                    clock=clock,
                    current_score=result["current_score"],
                    manual_override=True,
                    pace_choice=pace_choice
                )


def main():
    while True:
        print("1. Live prediction from API")
        print("2. Log completed bet result")
        print("3. Bet summary")
        print("4. Exit")

        choice = input("Choose option: ").strip()

        if choice == "1":
            live_prediction()
        elif choice == "2":
            log_bet_result()
        elif choice == "3":
            show_bet_summary()
        elif choice == "4":
            print("Goodbye.")
            break
        else:
            print("Invalid option.\n")


if __name__ == "__main__":
    main()