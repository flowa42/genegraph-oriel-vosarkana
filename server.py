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
    """
    Input (JSON):
    {
      "name": "Mică Scânteie",
      "birthDate": "1991-07-17",
      "birthTime": "13:40",
      "birthPlace": "Mexico City"
    }
    """
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

        # Example: compute Sun position
        lon, lat, dist, speed = swe.calc_ut(jd, swe.SUN)

        # Build profile result
        profile = {
            "name": name,
            "birth_date": birth_date,
            "birth_time": birth_time,
            "birth_place": birth_place,
            "sun": {
                "longitude": lon,
                "latitude": lat,
                "distance": dist,
                "speed": speed
            }
        }

        return jsonify(profile)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -----------------------
# Run
# -----------------------
if __name__ == "__main__":
    # Render assigns $PORT automatically
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
