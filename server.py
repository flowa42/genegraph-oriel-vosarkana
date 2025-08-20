# -*- coding: utf-8 -*-
"""
GeneGraph minimal server (single file)
- Flask API with one POST /compute-profile
- Skyfield ephemeris (auto-download de421.bsp)
- Optional geocoding; supports direct lat/lon/timezone to bypass network
- Outputs Gene Keys profile JSON and an SVG graph URL

Requirements (install once):
  pip install Flask requests python-dateutil timezonefinder pytz skyfield jplephem cairosvg

Run:
  py server.py          (Windows)
Then test:
  curl -X POST http://localhost:8080/compute-profile ^
    -H "Content-Type: application/json" ^
    -d "{\"name\":\"Test\",\"birthDate\":\"1991-07-17\",\"birthTime\":\"13:40\",\"birthPlace\":\"Mexico City\",\"lat\":19.4326,\"lon\":-99.1332,\"timezone\":\"America/Mexico_City\",\"designMode\":\"days\",\"includeHD\":true}"
"""

import os, json, math, uuid, pathlib, traceback
from datetime import datetime, timedelta
from dateutil import parser as dtparse

import requests
from flask import Flask, request, jsonify, send_from_directory
from timezonefinder import TimezoneFinder
import pytz
from pytz import AmbiguousTimeError, NonExistentTimeError

# Skyfield
from skyfield.api import load
from skyfield.framelib import ecliptic_frame

# ----------- App folders -----------
APP_DIR   = pathlib.Path(__file__).parent.resolve()
STATIC_DIR = APP_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)

# ----------- Skyfield ephemeris -----------
TS  = load.timescale()
EPH = load('de421.bsp')   # Skyfield will download and cache automatically (1900–2050)

# ----------- Constants -----------
SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
GATE_SPAN = 5.625        # degrees (360/64)
LINE_SPAN = GATE_SPAN / 6.0  # 0.9375°

# ----------- Gate ranges per sign (start/end in DMS strings) -----------
# Sourced from consolidated "Astrology positions of Human Design Gates" cheat sheet.
GATE_TABLE = {
    "Aries": [
      {"gate": 25, "start": "0°0'0\"", "end": "3°52'30\""},
      {"gate": 17, "start": "3°52'30\"", "end": "9°30'0\""},
      {"gate": 21, "start": "9°30'0\"", "end": "15°7'30\""},
      {"gate": 51, "start": "15°7'30\"", "end": "20°45'0\""},
      {"gate": 42, "start": "20°45'0\"", "end": "26°22'30\""},
      {"gate": 3,  "start": "26°22'30\"", "end": "30°0'0\""}
    ],
    "Taurus": [
      {"gate": 3,  "start": "0°0'0\"", "end": "2°0'0\""},
      {"gate": 27, "start": "2°0'0\"", "end": "7°37'30\""},
      {"gate": 24, "start": "7°37'30\"", "end": "13°15'0\""},
      {"gate": 2,  "start": "13°15'0\"", "end": "18°52'30\""},
      {"gate": 23, "start": "18°52'30\"", "end": "24°30'0\""},
      {"gate": 8,  "start": "24°30'0\"", "end": "30°0'0\""}
    ],
    "Gemini": [
      {"gate": 8,  "start": "0°0'0\"", "end": "0°7'30\""},
      {"gate": 20, "start": "0°7'30\"", "end": "5°45'0\""},
      {"gate": 16, "start": "5°45'0\"", "end": "11°22'30\""},
      {"gate": 35, "start": "11°22'30\"", "end": "17°0'0\""},
      {"gate": 45, "start": "17°0'0\"", "end": "22°37'30\""},
      {"gate": 12, "start": "22°37'30\"", "end": "28°15'0\""},
      {"gate": 15, "start": "28°15'0\"", "end": "30°0'0\""}
    ],
    "Cancer": [
      {"gate": 15, "start": "0°0'0\"", "end": "3°52'30\""},
      {"gate": 52, "start": "3°52'30\"", "end": "9°30'0\""},
      {"gate": 39, "start": "9°30'0\"", "end": "15°7'30\""},
      {"gate": 53, "start": "15°7'30\"", "end": "20°45'0\""},
      {"gate": 62, "start": "20°45'0\"", "end": "26°22'30\""},
      {"gate": 56, "start": "26°22'30\"", "end": "30°0'0\""}
    ],
    "Leo": [
      {"gate": 56, "start": "0°0'0\"", "end": "2°0'0\""},
      {"gate": 31, "start": "2°0'0\"", "end": "7°37'30\""},
      {"gate": 33, "start": "7°37'30\"", "end": "13°15'0\""},
      {"gate": 7,  "start": "13°15'0\"", "end": "18°52'30\""},
      {"gate": 4,  "start": "18°52'30\"", "end": "24°30'0\""},
      {"gate": 29, "start": "24°30'0\"", "end": "30°0'0\""}
    ],
    "Virgo": [
      {"gate": 29, "start": "0°0'0\"", "end": "0°7'30\""},
      {"gate": 59, "start": "0°7'30\"", "end": "5°45'0\""},
      {"gate": 40, "start": "5°45'0\"", "end": "11°22'30\""},
      {"gate": 64, "start": "11°22'30\"", "end": "17°0'0\""},
      {"gate": 47, "start": "17°0'0\"", "end": "22°37'30\""},
      {"gate": 6,  "start": "22°37'30\"", "end": "28°15'0\""},
      {"gate": 46, "start": "28°15'0\"", "end": "30°0'0\""}
    ],
    "Libra": [
      {"gate": 46, "start": "0°0'0\"", "end": "3°52'30\""},
      {"gate": 18, "start": "3°52'30\"", "end": "9°30'0\""},
      {"gate": 48, "start": "9°30'0\"", "end": "15°7'30\""},
      {"gate": 57, "start": "15°7'30\"", "end": "20°45'0\""},
      {"gate": 32, "start": "20°45'0\"", "end": "26°22'30\""},
      {"gate": 50, "start": "26°22'30\"", "end": "30°0'0\""}
    ],
    "Scorpio": [
      {"gate": 50, "start": "0°0'0\"", "end": "2°0'0\""},
      {"gate": 28, "start": "2°0'0\"", "end": "7°37'30\""},
      {"gate": 44, "start": "7°37'30\"", "end": "13°15'0\""},
      {"gate": 1,  "start": "13°15'0\"", "end": "18°52'30\""},
      {"gate": 43, "start": "18°52'30\"", "end": "24°30'0\""},
      {"gate": 14, "start": "24°30'0\"", "end": "30°0'0\""}
    ],
    "Sagittarius": [
      {"gate": 14, "start": "0°0'0\"", "end": "0°7'30\""},
      {"gate": 34, "start": "0°7'30\"", "end": "5°45'0\""},
      {"gate": 9,  "start": "5°45'0\"", "end": "11°22'30\""},
      {"gate": 5,  "start": "11°22'30\"", "end": "17°0'0\""},
      {"gate": 26, "start": "17°0'0\"", "end": "22°37'30\""},
      {"gate": 11, "start": "22°37'30\"", "end": "28°15'0\""},
      {"gate": 10, "start": "28°15'0\"", "end": "30°0'0\""}
    ],
    "Capricorn": [
      {"gate": 10, "start": "0°0'0\"", "end": "3°52'30\""},
      {"gate": 58, "start": "3°52'30\"", "end": "9°30'0\""},
      {"gate": 38, "start": "9°30'0\"", "end": "15°7'30\""},
      {"gate": 54, "start": "15°7'30\"", "end": "20°45'0\""},
      {"gate": 61, "start": "20°45'0\"", "end": "26°22'30\""},
      {"gate": 60, "start": "26°22'30\"", "end": "30°0'0\""}
    ],
    "Aquarius": [
      {"gate": 60, "start": "0°0'0\"", "end": "2°0'0\""},
      {"gate": 41, "start": "2°0'0\"", "end": "7°37'30\""},
      {"gate": 19, "start": "7°37'30\"", "end": "13°15'0\""},
      {"gate": 13, "start": "13°15'0\"", "end": "18°52'30\""},
      {"gate": 49, "start": "18°52'30\"", "end": "24°30'0\""},
      {"gate": 30, "start": "24°30'0\"", "end": "30°0'0\""}
    ],
    "Pisces": [
      {"gate": 30, "start": "0°0'0\"", "end": "0°7'30\""},
      {"gate": 55, "start": "0°7'30\"", "end": "5°45'0\""},
      {"gate": 37, "start": "5°45'0\"", "end": "11°22'30\""},
      {"gate": 63, "start": "11°22'30\"", "end": "17°0'0\""},
      {"gate": 22, "start": "17°0'0\"", "end": "22°37'30\""},
      {"gate": 36, "start": "22°37'30\"", "end": "28°15'0\""},
      {"gate": 25, "start": "28°15'0\"", "end": "30°0'0\""}
    ]
}

# ----------- HD channels (for optional type/authority) -----------
CHANNELS = [
  {"id":"1-8","gates":[1,8],"centers":["G","Throat"]},
  {"id":"2-14","gates":[2,14],"centers":["G","Sacral"]},
  {"id":"3-60","gates":[3,60],"centers":["Sacral","Root"]},
  {"id":"4-63","gates":[4,63],"centers":["Ajna","Head"]},
  {"id":"5-15","gates":[5,15],"centers":["Sacral","G"]},
  {"id":"6-59","gates":[6,59],"centers":["Solar Plexus","Sacral"]},
  {"id":"7-31","gates":[7,31],"centers":["G","Throat"]},
  {"id":"9-52","gates":[9,52],"centers":["Sacral","Root"]},
  {"id":"10-20","gates":[10,20],"centers":["G","Throat"]},
  {"id":"10-34","gates":[10,34],"centers":["G","Sacral"]},
  {"id":"10-57","gates":[10,57],"centers":["G","Spleen"]},
  {"id":"11-56","gates":[11,56],"centers":["Ajna","Throat"]},
  {"id":"12-22","gates":[12,22],"centers":["Throat","Solar Plexus"]},
  {"id":"13-33","gates":[13,33],"centers":["G","Throat"]},
  {"id":"16-48","gates":[16,48],"centers":["Throat","Spleen"]},
  {"id":"17-62","gates":[17,62],"centers":["Ajna","Throat"]},
  {"id":"18-58","gates":[18,58],"centers":["Spleen","Root"]},
  {"id":"19-49","gates":[19,49],"centers":["Root","Solar Plexus"]},
  {"id":"20-34","gates":[20,34],"centers":["Throat","Sacral"]},
  {"id":"20-57","gates":[20,57],"centers":["Throat","Spleen"]},
  {"id":"21-45","gates":[21,45],"centers":["Heart","Throat"]},
  {"id":"23-43","gates":[23,43],"centers":["Ajna","Throat"]},
  {"id":"24-61","gates":[24,61],"centers":["Ajna","Head"]},
  {"id":"25-51","gates":[25,51],"centers":["G","Heart"]},
  {"id":"26-44","gates":[26,44],"centers":["Heart","Spleen"]},
  {"id":"27-50","gates":[27,50],"centers":["Sacral","Spleen"]},
  {"id":"28-38","gates":[28,38],"centers":["Spleen","Root"]},
  {"id":"29-46","gates":[29,46],"centers":["Sacral","G"]},
  {"id":"30-41","gates":[30,41],"centers":["Solar Plexus","Root"]},
  {"id":"32-54","gates":[32,54],"centers":["Spleen","Root"]},
  {"id":"34-57","gates":[34,57],"centers":["Sacral","Spleen"]},
  {"id":"35-36","gates":[35,36],"centers":["Throat","Solar Plexus"]},
  {"id":"37-40","gates":[37,40],"centers":["Solar Plexus","Heart"]},
  {"id":"39-55","gates":[39,55],"centers":["Root","Solar Plexus"]},
  {"id":"42-53","gates":[42,53],"centers":["Sacral","Root"]},
  {"id":"47-64","gates":[47,64],"centers":["Ajna","Head"]}
]

# ----------- Spheres → planet/mode (Gene Keys official mapping) -----------
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
    "Core":       {"planet": "mars",  "mode": "design"}  # aka Vocation
  },
  "pearl": {
    "Culture": {"planet": "jupiter", "mode": "design"},
    "Pearl":   {"planet": "jupiter", "mode": "natal"},
    "Vocation": {"planet": "mars", "mode": "design"},    # alias of Core
    "Brand":   {"planet": "sun", "mode": "natal"}        # alias of Life's Work
  }
}

# ----------- SVG template -----------
SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 720">
  <defs>
    <style>
      .bg{fill:#0b0f14}
      .seq-activation{fill:#2ecc71;opacity:.18}
      .seq-venus{fill:#ff4d8d;opacity:.18}
      .seq-pearl{fill:#3ea7ff;opacity:.18}
      .node{fill:#0b0f14;stroke:#cfd8dc;stroke-width:2}
      .edge{stroke:#607d8b;stroke-width:2;fill:none}
      .label{font:500 16px/1.2 ui-sans-serif,system-ui; fill:#e8f1f5; text-anchor:middle}
      .sub{font:400 13px/1.2 ui-sans-serif,system-ui; fill:#a7bdc9}
      .title{font:700 20px/1 ui-sans-serif,system-ui; fill:#cfe9ff}
    </style>
  </defs>
  <rect class="bg" x="0" y="0" width="100%" height="100%"/>

  <circle cx="500" cy="160" r="140" class="seq-activation"/>
  <ellipse cx="280" cy="470" rx="170" ry="140" class="seq-venus"/>
  <ellipse cx="720" cy="470" rx="170" ry="140" class="seq-pearl"/>

  <path class="edge" d="M500 60 L640 160 L500 260 L360 160 Z"/>
  <path class="edge" d="M360 160 L500 60"/>
  <path class="edge" d="M640 160 L500 260"/>

  <circle class="node" cx="500" cy="60" r="34"/><text class="label" x="500" y="56">Life’s Work</text><text class="sub" x="500" y="76">{LW}</text>
  <circle class="node" cx="640" cy="160" r="34"/><text class="label" x="640" y="156">Evolution</text><text class="sub" x="640" y="176">{EV}</text>
  <circle class="node" cx="500" cy="260" r="34"/><text class="label" x="500" y="256">Radiance</text><text class="sub" x="500" y="276">{RA}</text>
  <circle class="node" cx="360" cy="160" r="34"/><text class="label" x="360" y="156">Purpose</text><text class="sub" x="360" y="176">{PU}</text>

  <path class="edge" d="M170 420 L280 380 L280 470 L280 560 L200 510"/>
  <circle class="node" cx="170" cy="420" r="30"/><text class="label" x="170" y="416">Attraction</text><text class="sub" x="170" y="436">{AT}</text>
  <circle class="node" cx="280" cy="380" r="30"/><text class="label" x="280" y="376">IQ</text><text class="sub" x="280" y="396">{IQ}</text>
  <circle class="node" cx="280" cy="470" r="30"/><text class="label" x="280" y="466">EQ</text><text class="sub" x="280" y="486">{EQ}</text>
  <circle class="node" cx="280" cy="560" r="30"/><text class="label" x="280" y="556">SQ</text><text class="sub" x="280" y="576">{SQ}</text>
  <circle class="node" cx="200" cy="510" r="30"/><text class="label" x="200" y="506">Core / Voc</text><text class="sub" x="200" y="526">{CO}</text>

  <path class="edge" d="M760 420 L680 510 L760 600 L840 510 Z"/>
  <circle class="node" cx="760" cy="420" r="30"/><text class="label" x="760" y="416">Brand</text><text class="sub" x="760" y="436">{BR}</text>
  <circle class="node" cx="680" cy="510" r="30"/><text class="label" x="680" y="506">Culture</text><text class="sub" x="680" y="526">{CU}</text>
  <circle class="node" cx="760" cy="600" r="30"/><text class="label" x="760" y="596">Pearl</text><text class="sub" x="760" y="616">{PE}</text>
  <circle class="node" cx="840" cy="510" r="30"/><text class="label" x="840" y="506">Vocation</text><text class="sub" x="840" y="526">{VO}</text>

  <text class="title" x="500" y="700">{TITLE}</text>
</svg>"""

# ----------- Helpers -----------
def dms_to_deg(dms: str) -> float:
    d, m, s = dms.replace("°"," ").replace("'"," ").replace("\""," ").split()
    return float(d) + float(m)/60.0 + float(s)/3600.0

# Build numeric intervals
SIGN_INTERVALS = {}
for sign, rows in GATE_TABLE.items():
    SIGN_INTERVALS[sign] = [{"gate": r["gate"], "start": dms_to_deg(r["start"]), "end": dms_to_deg(r["end"])} for r in rows]

def longitude_to_sign_deg(lon_deg: float):
    lon = lon_deg % 360.0
    sign_index = int(lon // 30.0)
    deg_in_sign = lon - sign_index*30.0
    return SIGNS[sign_index], sign_index, deg_in_sign, lon

def gate_line_from_longitude(lon_deg: float):
    """Map absolute ecliptic longitude to (gate, line) with correct line across sign boundaries."""
    sign, sidx, deg_in_sign, abs_deg = longitude_to_sign_deg(lon_deg)
    intervals = SIGN_INTERVALS[sign]
    target = None
    for r in intervals:
        if r["start"] <= deg_in_sign < r["end"]:
            target = r
            break
    if target is None:
        # edge case: exactly on 30° boundary
        target = intervals[-1]
    gate = target["gate"]
    # Compute global start degree of this gate (handle cross-sign)
    global_start = sidx * 30.0 + target["start"]
    # If gate continues from previous sign, fix start to that previous segment
    prev_sign = SIGNS[(sidx - 1) % 12]
    prev_last = SIGN_INTERVALS[prev_sign][-1]
    if prev_last["gate"] == gate and math.isclose(prev_last["end"], 30.0, abs_tol=1e-6):
        global_start = (sidx - 1) * 30.0 + prev_last["start"]

    offset = (abs_deg - global_start) % 360.0
    line = int(math.floor((offset + 1e-9) / LINE_SPAN)) + 1
    line = max(1, min(6, line))
    return gate, line, sign, deg_in_sign

def geocode_place(place: str):
    url = "https://nominatim.openstreetmap.org/search"
    r = requests.get(
        url,
        params={"q": place, "format": "json", "limit": 1},
        headers={"User-Agent": "GeneGraph/1.0 (contact: you@example.com)"},
        timeout=25
    )
    r.raise_for_status()
    arr = r.json()
    if not arr:
        raise ValueError("Place not found")
    return float(arr[0]["lat"]), float(arr[0]["lon"])

def tz_for_latlon(lat, lon, dt_local):
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lng=lon, lat=lat) or tf.closest_timezone_at(lng=lon, lat=lat)
    if not tzname:
        raise ValueError("Timezone not found")
    tz = pytz.timezone(tzname)
    try:
        localized = tz.localize(dt_local, is_dst=None)
    except AmbiguousTimeError:
        localized = tz.localize(dt_local, is_dst=True)
    except NonExistentTimeError:
        localized = tz.localize(dt_local + timedelta(hours=1), is_dst=True)
    return tzname, localized.astimezone(pytz.utc)

def ecliptic_longitude_deg(t, body: str):
    earth = EPH['earth']
    if body == "earth":
        # Earth longitude = Sun + 180 (geocentric)
        ast = earth.at(t).observe(EPH['sun']).apparent()
        lon, lat, dist = ast.frame_latlon(ecliptic_frame)
        return (lon.degrees + 180.0) % 360.0
    key = {
        "sun": "sun", "moon": "moon",
        "mercury": "mercury", "venus": "venus", "mars": "mars",
        "jupiter": "jupiter barycenter", "saturn": "saturn barycenter",
        "uranus": "uranus barycenter", "neptune": "neptune barycenter", "pluto": "pluto barycenter"
    }[body]
    ast = earth.at(t).observe(EPH[key]).apparent()
    lon, lat, dist = ast.frame_latlon(ecliptic_frame)
    return lon.degrees % 360.0

def design_time_from_days(birth_utc: datetime, days=88):
    return birth_utc - timedelta(days=days)

def design_time_from_solar_arc(birth_utc: datetime, target_arc=-88.0):
    # binary search in ±150d for when Sun has moved -88°
    t0 = TS.utc(birth_utc.year, birth_utc.month, birth_utc.day, birth_utc.hour, birth_utc.minute, birth_utc.second)
    sun0 = ecliptic_longitude_deg(t0, "sun")
    lo = birth_utc - timedelta(days=150)
    hi = birth_utc + timedelta(days=150)

    def arc_err(dt):
        t = TS.utc(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
        sun = ecliptic_longitude_deg(t, "sun")
        diff = ((sun - sun0 + 540.0) % 360.0) - 180.0
        return diff - target_arc

    for _ in range(50):
        mid = lo + (hi - lo)/2
        if arc_err(mid) > 0:
            lo = mid
        else:
            hi = mid
    return lo

def compute_bodies(dt_utc: datetime):
    t = TS.utc(dt_utc.year, dt_utc.month, dt_utc.day, dt_utc.hour, dt_utc.minute, dt_utc.second)
    out = {}
    for body in ["sun","moon","mercury","venus","mars","jupiter","saturn","uranus","neptune","pluto","earth"]:
        lon = ecliptic_longitude_deg(t, body)
        gate, line, sign, deg_in_sign = gate_line_from_longitude(lon)
        out[body] = {
            "lon": round(lon, 6),
            "sign": sign,
            "deg_in_sign": round(deg_in_sign, 6),
            "gate": gate,
            "line": line
        }
    return out

def build_gene_keys_profile(natal, design):
    def sphere_rec(seq, sphere, mp):
        planet = mp["planet"]; mode = mp["mode"]
        src = natal if mode == "natal" else design
        rec = src[planet]
        return {"sphere": sphere, "planet": planet, "mode": mode, "gk": rec["gate"], "line": rec["line"], "sign": rec["sign"], "lon": rec["lon"]}
    prof = {"activation": [], "venus": [], "pearl": []}
    for sph, mp in SPHERES["activation"].items():
        prof["activation"].append(sphere_rec("activation", sph, mp))
    for sph, mp in SPHERES["venus"].items():
        prof["venus"].append(sphere_rec("venus", sph, mp))
    for sph, mp in SPHERES["pearl"].items():
        prof["pearl"].append(sphere_rec("pearl", sph, mp))
    return prof

def compute_hd(natal, design):
    active = set()
    for src in (natal, design):
        for rec in src.values():
            active.add(rec["gate"])

    defined_channels = []
    defined_centers  = set()
    for ch in CHANNELS:
        a, b = ch["gates"]
        if a in active and b in active:
            defined_channels.append(ch["id"])
            for c in ch["centers"]:
                defined_centers.add(c)

    centers_list = sorted(defined_centers)

    # Type / Strategy / Authority (simplified canonical logic)
    has = {c: c in defined_centers for c in ["Head","Ajna","Throat","G","Heart","Spleen","Solar Plexus","Sacral","Root"]}

    def throat_has_motor():
        motors = {"Heart","Solar Plexus","Sacral","Root"}
        for ch in CHANNELS:
            if ch["id"] in defined_channels:
                if "Throat" in ch["centers"] and (motors & set(ch["centers"])):
                    return True
        return False

    if not centers_list:
        hd_type, strategy, authority = "Reflector", "Wait a lunar cycle (~28 days)", "Lunar"
    else:
        if has["Sacral"]:
            if throat_has_motor():
                hd_type, strategy = "Manifesting Generator", "Wait to respond, then inform"
            else:
                hd_type, strategy = "Generator", "Wait to respond"
        else:
            if throat_has_motor():
                hd_type, strategy = "Manifestor", "Inform before acting"
            else:
                hd_type, strategy = "Projector", "Wait for the invitation"

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

    gates_detail = []
    for src, side in [(natal,"natal"), (design,"design")]:
        for planet, rec in src.items():
            gates_detail.append({"side": side, "planet": planet, "gate": rec["gate"], "line": rec["line"], "sign": rec["sign"], "lon": rec["lon"]})

    return {
        "gates": gates_detail,
        "channels": defined_channels,
        "definedCenters": centers_list,
        "type": hd_type,
        "strategy": strategy,
        "authority": authority
    }

def render_svg(name, profile):
    def kk(r): return f"GK {r['gk']}.{r['line']}"
    A = {r["sphere"]: r for r in profile["activation"]}
    V = {r["sphere"]: r for r in profile["venus"]}
    P = {r["sphere"]: r for r in profile["pearl"]}

    tokens = {
        "LW": kk(A["LifesWork"]),
        "EV": kk(A["Evolution"]),
        "RA": kk(A["Radiance"]),
        "PU": kk(A["Purpose"]),
        "AT": kk(V["Attraction"]),
        "IQ": kk(V["IQ"]),
        "EQ": kk(V["EQ"]),
        "SQ": kk(V["SQ"]),
        "CO": kk(V["Core"]),
        "BR": kk(A["LifesWork"]),   # alias
        "CU": kk(P["Culture"]),
        "PE": kk(P["Pearl"]),
        "VO": kk(V["Core"]),        # alias
        "TITLE": f"{name} — Hologenetic Profile",
    }

    # Do a safe token replacement (no .format()), so CSS braces stay intact.
    svg = SVG_TEMPLATE
    for k, v in tokens.items():
        svg = svg.replace(f"{{{k}}}", str(v))

    fid = f"profile_{uuid.uuid4().hex}"
    svg_path = STATIC_DIR / f"{fid}.svg"
    svg_path.write_text(svg, encoding="utf-8")

    png_url = None
    try:
        import cairosvg
        png_path = STATIC_DIR / f"{fid}.png"
        cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(png_path))
        png_url = f"/assets/{png_path.name}"
    except Exception:
        pass

    return {"svg_url": f"/assets/{svg_path.name}", "png_url": png_url}


# ----------- Flask App -----------
app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({"ok": True}), 200

@app.route("/assets/<path:filename>")
def get_asset(filename):
    return send_from_directory(STATIC_DIR, filename, as_attachment=False)

@app.post("/compute-profile")
def compute_profile():
    try:
        payload = request.get_json(silent=True) or {}

        name        = (payload.get("name") or "Profile").strip()
        birth_date  = payload.get("birthDate")
        birth_time  = payload.get("birthTime", "00:00")
        birth_place = payload.get("birthPlace", "")
        design_mode = payload.get("designMode", "days")
        include_hd  = bool(payload.get("includeHD", False))

        if not birth_date or not birth_place:
            return jsonify({"error":"birthDate and birthPlace are required"}), 400

        dt_local = dtparse.parse(f"{birth_date} {birth_time}")

        # Bypass geocoding if lat/lon/timezone provided
        lat = payload.get("lat"); lon = payload.get("lon"); tzname = payload.get("timezone")
        if lat is not None and lon is not None and tzname:
            lat = float(lat); lon = float(lon)
            tz = pytz.timezone(tzname)
            try:
                localized = tz.localize(dt_local, is_dst=None)
            except AmbiguousTimeError:
                localized = tz.localize(dt_local, is_dst=True)
            except NonExistentTimeError:
                localized = tz.localize(dt_local + timedelta(hours=1), is_dst=True)
            dt_utc = localized.astimezone(pytz.utc)
        else:
            lat, lon = geocode_place(birth_place)
            tzname, dt_utc = tz_for_latlon(lat, lon, dt_local)

        dt_design = design_time_from_solar_arc(dt_utc) if design_mode == "solarArc" else design_time_from_days(dt_utc, 88)

        natal  = compute_bodies(dt_utc)
        design = compute_bodies(dt_design)
        profile = build_gene_keys_profile(natal, design)
        hd = compute_hd(natal, design) if include_hd else None
        assets = render_svg(name, profile)

        result = {
            "meta": {
                "input": {"name": name, "birthDate": birth_date, "birthTime": birth_time, "birthPlace": birth_place, "designMode": design_mode, "includeHD": include_hd},
                "geocode": {"lat": lat, "lon": lon, "timezone": tzname},
                "utc": {"birth": dt_utc.isoformat(), "design": dt_design.isoformat()}
            },
            "bodies": {"natal": natal, "design": design},
            "geneKeys": profile,
            "humanDesign": hd,
            "assets": {"profileSVG": assets["svg_url"], "profilePNG": assets["png_url"]}
        }
        return jsonify(result), 200

    except Exception as e:
        print("\n=== /compute-profile ERROR ===")
        print(repr(e))
        traceback.print_exc()
        print("=== /compute-profile ERROR END ===\n")
        return jsonify({"error": type(e).__name__, "detail": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    # 0.0.0.0 so tunnels (ngrok/cloudflare) can reach it
    app.run(host="0.0.0.0", port=port)
