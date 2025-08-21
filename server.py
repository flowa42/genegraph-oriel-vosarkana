import os
from math import floor, isclose
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import swisseph as swe
import pytz

# -----------------------
# Flask app
# -----------------------
app = Flask(__name__)

# -----------------------
# Swiss Ephemeris
# -----------------------
def init_ephemeris():
    # Use local dir; Render caches ephemeris after first run if you upload kernels.
    swe.set_ephe_path(".")
init_ephemeris()

# -----------------------
# HD / GK tables
# -----------------------
SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
GATE_SPAN = 360.0 / 64.0            # 5.625°
LINE_SPAN = GATE_SPAN / 6.0         # 0.9375°

# Compact gate table by sign (start/end in degrees within sign).
# These segments are a standard consolidated mapping of HD gates to tropical zodiac.
GATE_TABLE = {
    "Aries":[{"gate":25,"start":0.0,"end":3.875},{"gate":17,"start":3.875,"end":9.5},{"gate":21,"start":9.5,"end":15.125},{"gate":51,"start":15.125,"end":20.75},{"gate":42,"start":20.75,"end":26.375},{"gate":3,"start":26.375,"end":30.0}],
    "Taurus":[{"gate":3,"start":0.0,"end":2.0},{"gate":27,"start":2.0,"end":7.625},{"gate":24,"start":7.625,"end":13.25},{"gate":2,"start":13.25,"end":18.875},{"gate":23,"start":18.875,"end":24.5},{"gate":8,"start":24.5,"end":30.0}],
    "Gemini":[{"gate":8,"start":0.0,"end":0.125},{"gate":20,"start":0.125,"end":5.75},{"gate":16,"start":5.75,"end":11.375},{"gate":35,"start":11.375,"end":17.0},{"gate":45,"start":17.0,"end":22.625},{"gate":12,"start":22.625,"end":28.25},{"gate":15,"start":28.25,"end":30.0}],
    "Cancer":[{"gate":15,"start":0.0,"end":3.875},{"gate":52,"start":3.875,"end":9.5},{"gate":39,"start":9.5,"end":15.125},{"gate":53,"start":15.125,"end":20.75},{"gate":62,"start":20.75,"end":26.375},{"gate":56,"start":26.375,"end":30.0}],
    "Leo":[{"gate":56,"start":0.0,"end":2.0},{"gate":31,"start":2.0,"end":7.625},{"gate":33,"start":7.625,"end":13.25},{"gate":7,"start":13.25,"end":18.875},{"gate":4,"start":18.875,"end":24.5},{"gate":29,"start":24.5,"end":30.0}],
    "Virgo":[{"gate":29,"start":0.0,"end":0.125},{"gate":59,"start":0.125,"end":5.75},{"gate":40,"start":5.75,"end":11.375},{"gate":64,"start":11.375,"end":17.0},{"gate":47,"start":17.0,"end":22.625},{"gate":6,"start":22.625,"end":28.25},{"gate":46,"start":28.25,"end":30.0}],
    "Libra":[{"gate":46,"start":0.0,"end":3.875},{"gate":18,"start":3.875,"end":9.5},{"gate":48,"start":9.5,"end":15.125},{"gate":57,"start":15.125,"end":20.75},{"gate":32,"start":20.75,"end":26.375},{"gate":50,"start":26.375,"end":30.0}],
    "Scorpio":[{"gate":50,"start":0.0,"end":2.0},{"gate":28,"start":2.0,"end":7.625},{"gate":44,"start":7.625,"end":13.25},{"gate":1,"start":13.25,"end":18.875},{"gate":43,"start":18.875,"end":24.5},{"gate":14,"start":24.5,"end":30.0}],
    "Sagittarius":[{"gate":14,"start":0.0,"end":0.125},{"gate":34,"start":0.125,"end":5.75},{"gate":9,"start":5.75,"end":11.375},{"gate":5,"start":11.375,"end":17.0},{"gate":26,"start":17.0,"end":22.625},{"gate":11,"start":22.625,"end":28.25},{"gate":10,"start":28.25,"end":30.0}],
    "Capricorn":[{"gate":10,"start":0.0,"end":3.875},{"gate":58,"start":3.875,"end":9.5},{"gate":38,"start":9.5,"end":15.125},{"gate":54,"start":15.125,"end":20.75},{"gate":61,"start":20.75,"end":26.375},{"gate":60,"start":26.375,"end":30.0}],
    "Aquarius":[{"gate":60,"start":0.0,"end":2.0},{"gate":41,"start":2.0,"end":7.625},{"gate":19,"start":7.625,"end":13.25},{"gate":13,"start":13.25,"end":18.875},{"gate":49,"start":18.875,"end":24.5},{"gate":30,"start":24.5,"end":30.0}],
    "Pisces":[{"gate":30,"start":0.0,"end":0.125},{"gate":55,"start":0.125,"end":5.75},{"gate":37,"start":5.75,"end":11.375},{"gate":63,"start":11.375,"end":17.0},{"gate":22,"start":17.0,"end":22.625},{"gate":36,"start":22.625,"end":28.25},{"gate":25,"start":28.25,"end":30.0}]
}

# Channels (subset sufficient to derive Type/Authority cleanly)
CHANNELS = [
  {"id":"1-8","g":[1,8],"c":["G","Throat"]},
  {"id":"2-14","g":[2,14],"c":["G","Sacral"]},
  {"id":"3-60","g":[3,60],"c":["Sacral","Root"]},
  {"id":"4-63","g":[4,63],"c":["Ajna","Head"]},
  {"id":"5-15","g":[5,15],"c":["Sacral","G"]},
  {"id":"6-59","g":[6,59],"c":["Solar Plexus","Sacral"]},
  {"id":"7-31","g":[7,31],"c":["G","Throat"]},
  {"id":"9-52","g":[9,52],"c":["Sacral","Root"]},
  {"id":"10-20","g":[10,20],"c":["G","Throat"]},
  {"id":"10-34","g":[10,34],"c":["G","Sacral"]},
  {"id":"10-57","g":[10,57],"c":["G","Spleen"]},
  {"id":"11-56","g":[11,56],"c":["Ajna","Throat"]},
  {"id":"12-22","g":[12,22],"c":["Throat","Solar Plexus"]},
  {"id":"13-33","g":[13,33],"c":["G","Throat"]},
  {"id":"16-48","g":[16,48],"c":["Throat","Spleen"]},
  {"id":"17-62","g":[17,62],"c":["Ajna","Throat"]},
  {"id":"18-58","g":[18,58],"c":["Spleen","Root"]},
  {"id":"19-49","g":[19,49],"c":["Root","Solar Plexus"]},
  {"id":"20-34","g":[20,34],"c":["Throat","Sacral"]},
  {"id":"20-57","g":[20,57],"c":["Throat","Spleen"]},
  {"id":"21-45","g":[21,45],"c":["Heart","Throat"]},
  {"id":"23-43","g":[23,43],"c":["Ajna","Throat"]},
  {"id":"24-61","g":[24,61],"c":["Ajna","Head"]},
  {"id":"25-51","g":[25,51],"c":["G","Heart"]},
  {"id":"26-44","g":[26,44],"c":["Heart","Spleen"]},
  {"id":"27-50","g":[27,50],"c":["Sacral","Spleen"]},
  {"id":"28-38","g":[28,38],"c":["Spleen","Root"]},
  {"id":"29-46","g":[29,46],"c":["Sacral","G"]},
  {"id":"30-41","g":[30,41],"c":["Solar Plexus","Root"]},
  {"id":"32-54","g":[32,54],"c":["Spleen","Root"]},
  {"id":"34-57","g":[34,57],"c":["Sacral","Spleen"]},
  {"id":"35-36","g":[35,36],"c":["Throat","Solar Plexus"]},
  {"id":"37-40","g":[37,40],"c":["Solar Plexus","Heart"]},
  {"id":"39-55","g":[39,55],"c":["Root","Solar Plexus"]},
  {"id":"42-53","g":[42,53],"c":["Sacral","Root"]},
  {"id":"47-64","g":[47,64],"c":["Ajna","Head"]},
]

SPHERES = {
  "activation": {
    "LifesWork": {"planet": "sun", "mode": "natal"},
    "Evolution": {"planet": "earth", "mode": "natal"},
    "Radiance":  {"planet": "sun", "mode": "design"},
    "Purpose":   {"planet": "earth", "mode": "design"}
  },
  "venus": {
    "Attraction": {"planet": "moon",  "mode": "design"},
    "IQ":         {"planet": "venus", "mode": "natal"},
    "EQ":         {"planet": "mars",  "mode": "natal"},
    "SQ":         {"planet": "venus", "mode": "design"},
    "Core":       {"planet": "mars",  "mode": "design"}
  },
  "pearl": {
    "Culture": {"planet": "jupiter", "mode": "design"},
    "Pearl":   {"planet": "jupiter", "mode": "natal"},
    "Vocation": {"planet": "mars", "mode": "design"},
    "Brand":   {"planet": "sun", "mode": "natal"}
  }
}

# -----------------------
# Helpers
# -----------------------
def to_utc(birth_date: str, birth_time: str, timezone: str | None):
    """Return aware UTC datetime and tz name. If timezone missing, assume UTC."""
    tzname = timezone or "UTC"
    tz = pytz.timezone(tzname)
    dt_local = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")
    dt_utc = tz.localize(dt_local).astimezone(pytz.utc)
    return dt_utc, tzname

def long_to_sign_deg(lon_deg: float):
    lon = lon_deg % 360.0
    sidx = int(lon // 30.0)
    deg_in_sign = lon - sidx*30.0
    return SIGNS[sidx], sidx, deg_in_sign, lon

def gate_line_from_longitude(lon_deg: float):
    """Map ecliptic longitude → (gate, line, sign, deg_in_sign)."""
    sign, sidx, deg_in_sign, abs_deg = long_to_sign_deg(lon_deg)
    intervals = GATE_TABLE[sign]
    segment = None
    for r in intervals:
        if r["start"] <= deg_in_sign < r["end"]:
            segment = r
            break
    if segment is None:
        segment = intervals[-1]
    gate = segment["gate"]
    # global start for line calc (handle cross-sign continuation)
    global_start = sidx * 30.0 + segment["start"]
    prev_sign = SIGNS[(sidx - 1) % 12]
    prev_last = GATE_TABLE[prev_sign][-1]
    if prev_last["gate"] == gate and isclose(prev_last["end"], 30.0, abs_tol=1e-6):
        global_start = (sidx - 1) * 30.0 + prev_last["start"]
    offset = (abs_deg - global_start) % 360.0
    line = int(floor((offset + 1e-9) / LINE_SPAN)) + 1
    line = max(1, min(6, line))
    return gate, line, sign, deg_in_sign

def jd_from_datetime_utc(dt_utc: datetime) -> float:
    return swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour + dt_utc.minute/60.0 + dt_utc.second/3600.0)

def planet_longitudes(dt_utc: datetime):
    jd = jd_from_datetime_utc(dt_utc)
    planets = {
        "sun": swe.SUN, "moon": swe.MOON, "mercury": swe.MERCURY, "venus": swe.VENUS, "mars": swe.MARS,
        "jupiter": swe.JUPITER, "saturn": swe.SATURN, "uranus": swe.URANUS, "neptune": swe.NEPTUNE, "pluto": swe.PLUTO
    }
    out = {}
    for k, pid in planets.items():
        res, ret = swe.calc_ut(jd, pid, swe.FLG_SWIEPH | swe.FLG_SPEED)
        lon = res[0] % 360.0
        out[k] = lon
    # Earth = Sun + 180 (geocentric)
    out["earth"] = (out["sun"] + 180.0) % 360.0
    # Lunar Nodes (mean node is standard in HD); South = North + 180
    node_res, _ = swe.calc_ut(jd, swe.MEAN_NODE)
    north = node_res[0] % 360.0
    out["north_node"] = north
    out["south_node"] = (north + 180.0) % 360.0
    return out

def hd_points(dt_utc: datetime):
    longs = planet_longitudes(dt_utc)
    pts = {}
    for name, lon in longs.items():
        g,l,sign,deg = gate_line_from_longitude(lon)
        pts[name] = {"lon": round(lon,6), "sign": sign, "deg_in_sign": round(deg,6), "gate": g, "line": l}
    return pts

def design_time_88_days(dt_utc: datetime):
    return dt_utc - timedelta(days=88)

def build_gene_keys(natal: dict, design: dict):
    def pick(m):  # mode → table
        return natal if m=="natal" else design
    prof = {"activation":[], "venus":[], "pearl":[]}
    for sph, mp in SPHERES["activation"].items():
        rec = pick(mp["mode"])[mp["planet"]]
        prof["activation"].append({"sphere":sph,"planet":mp["planet"],"mode":mp["mode"],"gk":rec["gate"],"line":rec["line"],"sign":rec["sign"],"lon":rec["lon"]})
    for sph, mp in SPHERES["venus"].items():
        rec = pick(mp["mode"])[mp["planet"]]
        prof["venus"].append({"sphere":sph,"planet":mp["planet"],"mode":mp["mode"],"gk":rec["gate"],"line":rec["line"],"sign":rec["sign"],"lon":rec["lon"]})
    for sph, mp in SPHERES["pearl"].items():
        rec = pick(mp["mode"])[mp["planet"]]
        prof["pearl"].append({"sphere":sph,"planet":mp["planet"],"mode":mp["mode"],"gk":rec["gate"],"line":rec["line"],"sign":rec["sign"],"lon":rec["lon"]})
    return prof

def compute_hd_summary(natal: dict, design: dict):
    active_gates = {rec["gate"] for rec in natal.values()} | {rec["gate"] for rec in design.values()}
    defined_channels = []
    centers = set()
    for ch in CHANNELS:
        a,b = ch["g"]
        if a in active_gates and b in active_gates:
            defined_channels.append(ch["id"])
            centers.update(ch["c"])
    has = {c:(c in centers) for c in ["Head","Ajna","Throat","G","Heart","Spleen","Solar Plexus","Sacral","Root"]}

    # Type / Strategy (simplified canonical logic)
    def throat_has_motor():
        motors = {"Heart","Solar Plexus","Sacral","Root"}
        for ch in CHANNELS:
            if ch["id"] in defined_channels:
                if "Throat" in ch["c"] and (motors & set(ch["c"])):
                    return True
        return False

    if not centers:
        hd_type, strategy = "Reflector", "Wait a lunar cycle (~28 days)"
    else:
        if has["Sacral"]:
            hd_type  = "Manifesting Generator" if throat_has_motor() else "Generator"
            strategy = "Wait to respond" if hd_type=="Generator" else "Wait to respond, then inform"
        else:
            hd_type  = "Manifestor" if throat_has_motor() else "Projector"
            strategy = "Inform before acting" if hd_type=="Manifestor" else "Wait for the invitation"

    # Authority
    if has["Solar Plexus"]:
        authority = "Emotional"
    elif has["Sacral"]:
        authority = "Sacral"
    elif has["Spleen"]:
        authority = "Splenic"
    elif has["Heart"]:
        authority = "Ego"
    elif has["G"] and has["Throat"]:
        authority = "Self-Projected"
    else:
        authority = "Environmental"

    # Detail gates list
    gates_detail = []
    for side, table in [("natal", natal), ("design", design)]:
        for planet, rec in table.items():
            gates_detail.append({"side":side,"planet":planet,"gate":rec["gate"],"line":rec["line"],"sign":rec["sign"],"lon":rec["lon"]})

    return {
        "type": hd_type,
        "strategy": strategy,
        "authority": authority,
        "definedCenters": sorted(list(centers)),
        "channels": sorted(defined_channels),
        "gates": gates_detail
    }

# -----------------------
# Routes
# -----------------------
@app.get("/")
def health():
    return jsonify({"status":"GeneGraph server is running ✅"})

@app.post("/compute-profile")
def compute_profile():
    """
    Required JSON:
      birthDate (YYYY-MM-DD)
      birthTime (HH:MM, 24h)
    Optional:
      name (label), timezone (IANA, e.g. "America/Mexico_City")
    Note: HD planetary positions are geocentric and not location-dependent; timezone only converts local time to UTC correctly.
    """
    try:
        payload = request.get_json(silent=True) or {}
        name       = (payload.get("name") or "Profile").strip()
        birth_date = payload.get("birthDate")
        birth_time = payload.get("birthTime", "12:00")
        timezone   = payload.get("timezone")  # optional IANA tz; if missing we assume UTC

        if not birth_date:
            return jsonify({"error":"birthDate is required (YYYY-MM-DD)"}), 400

        dt_utc, tzname = to_utc(birth_date, birth_time, timezone)
        dt_design = design_time_88_days(dt_utc)

        natal  = hd_points(dt_utc)
        design = hd_points(dt_design)

        gene_keys = build_gene_keys(natal, design)
        hd = compute_hd_summary(natal, design)

        return jsonify({
            "meta": {
                "input": {"name":name, "birthDate":birth_date, "birthTime":birth_time, "timezone": tzname or "UTC"},
                "utc": {"birth": dt_utc.isoformat(), "design": dt_design.isoformat()}
            },
            "bodies": {"natal": natal, "design": design},
            "geneKeys": gene_keys,
            "humanDesign": hd
        }), 200

    except Exception as e:
        return jsonify({"error": type(e).__name__, "detail": str(e)}), 500


if __name__ == "__main__":
    # Local run
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
