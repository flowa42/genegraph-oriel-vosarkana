import os
from flask import Flask, request, jsonify
import swisseph as swe
from datetime import datetime

# -----------------------
# Flask app
# -----------------------
app = Flask(__name__)

# -----------------------
# Ephemeris setup
# -----------------------
def load_ephemeris():
    try:
        swe.set_ephe_path(".")
    except Exception as e:
        raise RuntimeError(f"Failed to set ephemeris: {e}")

load_ephemeris()

# -----------------------
# Routes
# -----------------------

@app.route("/", methods=["GET"])
def index():
    """Health check endpoint for Render."""
    return jsonify({"status": "GeneGraph server is running ✅"})

@app.route("/compute-profile", methods=["POST"])
def compute_profile():
    try:
        data = request.json or {}

        name = data.get("name", "Unknown")
        birth_date = data.get("birthDate")  # YYYY-MM-DD
        birth_time = data.get("birthTime", "12:00")  # fallback to noon
        birth_place = data.get("birthPlace", "Unknown")

        if not birth_date:
            return jsonify({"error": "birthDate is required (YYYY-MM-DD)"}), 400

        # Parse datetime
        dt_str = f"{birth_date} {birth_time}"
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")

        # Julian Day
        jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0)

        planets = {
            "Sun": swe.SUN,
            "Moon": swe.MOON,
            "Mercury": swe.MERCURY,
            "Venus": swe.VENUS,
            "Mars": swe.MARS,
            "Jupiter": swe.JUPITER,
            "Saturn": swe.SATURN,
            "Uranus": swe.URANUS,
            "Neptune": swe.NEPTUNE,
            "Pluto": swe.PLUTO,
        }

        results = {}
        for name_key, planet_id in planets.items():
            try:
                pos = swe.calc_ut(jd, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)[0]
                results[name_key] = {
                    "longitude": pos[0],
                    "latitude": pos[1],
                    "distance": pos[2],
                    "speed_longitude": pos[3],
                }
            except Exception as e:
                results[name_key] = {"error": str(e)}

        profile = {
            "name": name,
            "birth_date": birth_date,
            "birth_time": birth_time,
            "birth_place": birth_place,
            "planets": results,
        }

        return jsonify(profile)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
