import requests

LIVE_URL = "https://api-h2h.hudstats.com/v1/live/nba"


# ---------- API ----------
def fetch_live_games():
    response = requests.get(LIVE_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_match_details(external_id):
    url = f"{LIVE_URL}?external_id={external_id}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


# ---------- HELPERS ----------
def quarter_clock_to_minutes_played(quarter, clock_str):
    mins, secs = map(int, clock_str.split(":"))
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


# ---------- MODEL ----------
def extract_model_stats(details):
    a_stats = details["participantAStats"]
    b_stats = details["participantBStats"]

    historical_total = a_stats["avgPoints"] + b_stats["avgPoints"]
    historical_pace = historical_total / 48

    return {
        "historical_total": historical_total,
        "historical_pace": historical_pace,
        "form_a": a_stats.get("matchForm", []),
        "form_b": b_stats.get("matchForm", []),
        "h2h": details.get("h2H", []),
    }


def predict_total(current_score, minutes_played, historical_pace):
    current_pace = current_score / minutes_played
    blended_pace = (0.55 * current_pace) + (0.45 * historical_pace)

    minutes_left = 48 - minutes_played
    return current_score + (blended_pace * minutes_left)


def adjust_prediction(prediction, form_a, form_b, h2h, score_diff, minutes_left):
    form_edge = form_score(form_a[:5]) + form_score(form_b[:5])
    prediction += form_edge * 0.4

    h2h_edge = sum(1 if x == "w" else -1 for x in h2h)
    prediction += h2h_edge * 0.2

    if score_diff <= 5 and minutes_left <= 3:
        prediction += 6
    elif score_diff >= 15 and minutes_left <= 6:
        prediction -= 8

    return prediction


def betting_decision(game, minutes_played, vegas_line):
    current_score = game["teamAScore"] + game["teamBScore"]
    score_diff = abs(game["teamAScore"] - game["teamBScore"])

    details = fetch_match_details(game["externalId"])
    stats = extract_model_stats(details)

    prediction = predict_total(
        current_score=current_score,
        minutes_played=minutes_played,
        historical_pace=stats["historical_pace"]
    )

    minutes_left = 48 - minutes_played

    prediction = adjust_prediction(
        prediction,
        stats["form_a"],
        stats["form_b"],
        stats["h2h"],
        score_diff,
        minutes_left
    )

    edge = prediction - vegas_line

    if edge > 5:
        recommendation = "🔥 BET OVER"
    elif edge < -5:
        recommendation = "❄️ BET UNDER"
    else:
        recommendation = "⏸️ NO BET"

    return {
        "recommendation": recommendation,
        "prediction": round(prediction, 1),
        "edge": round(edge, 1),
        "historical_total": round(stats["historical_total"], 1),
    }


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


def main():
    games = fetch_live_games()
    live_games = [g for g in games if g["status"] == "live"]

    show_games(live_games)

    choice = int(input("Select game number: "))
    game = live_games[choice - 1]

    quarter = int(input("Quarter (1-4): "))
    clock = input("Clock remaining (mm:ss): ")
    vegas_line = float(input("Live O/U line: "))

    minutes_played = quarter_clock_to_minutes_played(quarter, clock)

    result = betting_decision(game, minutes_played, vegas_line)

    print("\n----- RESULT -----")
    print("Historical Total:", result["historical_total"])
    print("Prediction:", result["prediction"])
    print("Edge:", result["edge"])
    print(result["recommendation"])
    print("------------------\n")


if __name__ == "__main__":
    main()