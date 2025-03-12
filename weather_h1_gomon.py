import datetime as dt
import json
import requests
from flask import Flask, jsonify, request

API_TOKEN = ""
MISTRAL_AI_API_TOKEN = ""
WEATHER_RSA_KEY = ""

app = Flask(__name__)


class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv["message"] = self.message
        return rv


def ai_recommend_activities(temp_c, wind_kph, humidity, pressure_mb):
    weather_description = (f"What outdoor activities do you recommend, "
                           f"based on this weather:"
                           f"Temperature: {temp_c}°C, "
                           f"Wind speed: {wind_kph} km/h, "
                           f"Humidity: {humidity}%, "
                           f"Pressure: {pressure_mb} mb."
                           f"Answer shortly with few sentences.")

    url = "https://api.mistral.ai/v1/chat/completions"

    payload = {
        "model": "mistral-tiny",
        "messages": [{"role": "user", "content": weather_description}],
        "temperature": 0.5,
        "top_p": 1,
        "max_tokens": 200
    }

    headers = {
        "Authorization": f"Bearer {MISTRAL_AI_API_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        return f"Error: {response.status_code}, {response.text}"
    else:
        return (response.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "No recommendations generated."))


def check_date(date_str: str):
    try:
        dt.date.fromisoformat(date_str)
        return True
    except ValueError:
        return False


def convert_f_to_c(fahrenheit: float):
    return float(fahrenheit - 32) * 5 / 9


def get_weather(location: str, date: str):
    url_base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    url = f"{url_base_url}/{location}/{date}?key={WEATHER_RSA_KEY}"

    headers = {"X-Api-Key": WEATHER_RSA_KEY}

    response = requests.get(url, headers=headers)

    if response.status_code == requests.codes.ok:
        return json.loads(response.text)
    else:
        raise InvalidUsage(response.text, status_code=response.status_code)


@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route("/")
def home_page():
    return "<p><h2>KMA H1: weather python Saas.</h2></p>"


@app.route("/content/api/v1/integration/generate", methods=["POST"])
def weather_endpoint():
    json_data = request.get_json()

    required_info = ["token", "requester_name", "location", "date"]
    for field in required_info:
        if json_data.get(field) is None:
            raise InvalidUsage(f"{field} is required", status_code=400)

    token = json_data.get("token")
    requester_name = json_data.get("requester_name")
    location = json_data.get("location")
    date = json_data.get("date")

    if token != API_TOKEN:
        raise InvalidUsage("wrong API token", status_code=403)

    if not check_date(json_data.get("date")):
        raise InvalidUsage("invalid date", status_code=400)

    weather = get_weather(location, date)

    timestamp = dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    temp_c = round(convert_f_to_c(weather.get("days")[0].get("temp")), 1)
    wind_kph = weather.get("days")[0].get("windspeed")
    pressure_mb = weather.get("days")[0].get("pressure")
    humidity = weather.get("days")[0].get("humidity")

    hourly_information = weather.get("days")[0].get("hours")
    hourly_sorted = []

    if hourly_information is not None:
        for i in range(0, len(hourly_information), 6):
            hour = hourly_information[i]
            hourly_sorted.append({
                "datetime": hour.get("datetime"),
                "icon": hour.get("icon"),
                "temp_c": round(convert_f_to_c(hour.get("temp")), 1)
            })
    else:
        hourly_sorted.append("No hourly information")

    activity_recommendation = ai_recommend_activities(temp_c, wind_kph, humidity, pressure_mb)

    result = {
        "requester_name": requester_name,
        "timestamp": timestamp,
        "location": location,
        "date": date,
        "weather": {
            "temp_c": temp_c,
            "wind_kph": wind_kph,
            "pressure_mb": pressure_mb,
            "humidity": humidity,
            "weather_for_every_6_hours": hourly_sorted
        },
        "recommendations": activity_recommendation
    }

    return jsonify(result)
