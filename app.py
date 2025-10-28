from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import openai, os, sqlite3
from dateutil import parser
# ---------------- APP CONFIG ---------------- #
app = Flask(__name__)

# Load API keys from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Path for local database
DB_PATH = os.path.join(os.getcwd(), 'appointments.db')

# ---------------- DATABASE SETUP ---------------- #
def init_db():
    """Initialize SQLite database for storing appointments."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    date TEXT,
                    time TEXT,
                    reason TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

# ---------------- ROUTES ---------------- #
@app.route("/voice", methods=['POST', 'GET'])
def voice():
    """Handle incoming calls and ask for the user's name."""
    if request.method == 'GET':
        return "✅ /voice endpoint reachable (GET for debug)"

    response = VoiceResponse()
    gather = Gather(input='speech', action='/handle_name', method='POST')
    gather.say("Hello! This is your AI assistant. Please tell me your name to book an appointment.")
    response.append(gather)
    response.redirect('/voice')  # repeat if no input
    return Response(str(response), mimetype='text/xml')


@app.route("/handle_name", methods=['POST', 'GET'])
@app.route("/handle_name", methods=['POST', 'GET'])
def handle_name():
    """Capture the user's name and ask for appointment date."""
    if request.method == 'GET':
        return "✅ /handle_name endpoint reachable (GET for debug)"

    # ---------------- DEBUG INFO ---------------- #
    print("🧩 request.content_type =", request.content_type)
    print("🧩 request.data =", request.data)
    print("🧩 request.json =", request.json)
    print("🧩 request.form =", request.form)

    # ---------------- NAME EXTRACTION ---------------- #
    name = None
    if request.is_json and request.json:
        name = request.json.get('SpeechResult', '').strip()
    else:
        name = request.form.get('SpeechResult', '').strip()

    print("🧩 Extracted name =", name)

    response = VoiceResponse()

    # ---------------- MAIN LOGIC ---------------- #
    if name:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO appointments (name, date, time, reason) VALUES (?, ?, ?, ?)", (name, '', '', ''))
        conn.commit()
        appointment_id = c.lastrowid
        conn.close()

        gather = Gather(input='speech', action=f'/handle_date?aid={appointment_id}', method='POST')
        gather.say(f"Nice to meet you {name}! On what date would you like to schedule your appointment?")
        response.append(gather)
    else:
        response.say("Sorry, I didn't catch that. Please say your name again.")
        response.redirect('/voice')

    return Response(str(response), mimetype='text/xml')



@app.route("/handle_date", methods=['POST', 'GET'])


@app.route("/handle_date", methods=["GET", "POST"])
def handle_date():
    """Capture the appointment date and ask for time."""
    if request.method == 'GET':
        return "✅ /handle_date endpoint reachable (GET for debug)"

    data = request.get_json(force=True, silent=True) or {}
    date_input = data.get("SpeechResult", "").strip()
    aid = request.args.get("aid", None)

    response = VoiceResponse()

    if date_input and aid:
        try:
            parsed_date = parser.parse(date_input, fuzzy=True).strftime("%Y-%m-%d")
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE appointments SET date=? WHERE id=?", (parsed_date, aid))
            conn.commit()
            conn.close()

            gather = Gather(input='speech', action=f'/handle_time?aid={aid}', method='POST')
            gather.say(f"Got it. What time on {parsed_date} would you prefer?")
            response.append(gather)
        except Exception as e:
            print("⚠️ Date parsing error:", e)
            response.say("Sorry, could you please repeat the date?")
            response.redirect(f"/handle_date?aid={aid}")
    else:
        response.say("Sorry, I didn't catch that date. Please repeat it.")
        response.redirect(f"/handle_date?aid={aid}")

    return Response(str(response), mimetype='text/xml')



@app.route("/handle_time", methods=['POST', 'GET'])
def handle_time():
    """Capture time and ask for reason."""
    if request.method == 'GET':
        return "✅ /handle_time endpoint reachable (GET for debug)"

    # Support both JSON and form-encoded data
    time_input = (request.form.get('SpeechResult') or
                  (request.json.get('SpeechResult') if request.is_json else '')).strip()
    appointment_id = request.args.get('aid')
    response = VoiceResponse()

    if time_input and appointment_id:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE appointments SET time = ? WHERE id = ?", (time_input, appointment_id))
        conn.commit()
        conn.close()

        gather = Gather(input='speech', action=f'/handle_reason?aid={appointment_id}', method='POST')
        gather.say(f"Okay, {time_input} works. Could you please tell me the reason for your appointment?")
        response.append(gather)
    else:
        response.say("Sorry, please say the time again.")
        response.redirect(f'/handle_time?aid={appointment_id}')

    return Response(str(response), mimetype='text/xml')


@app.route("/handle_reason", methods=['POST', 'GET'])
def handle_reason():
    """Capture reason for the appointment and confirm booking."""
    if request.method == 'GET':
        return "✅ /handle_reason endpoint reachable (GET for debug)"

    # Handle both JSON and form data
    reason = (request.form.get('SpeechResult') or
              (request.json.get('SpeechResult') if request.is_json else '')).strip()
    appointment_id = request.args.get('aid')
    response = VoiceResponse()

    if reason and appointment_id:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE appointments SET reason = ? WHERE id = ?", (reason, appointment_id))
        conn.commit()
        conn.close()

        # Fetch appointment details for confirmation
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT name, date, time FROM appointments WHERE id = ?", (appointment_id,))
        appointment = c.fetchone()
        conn.close()

        if appointment:
            name, date, time = appointment
            response.say(f"Thank you {name}! Your appointment on {date} at {time} for {reason} has been booked successfully.")
        else:
            response.say("Something went wrong while retrieving your appointment details.")
    else:
        response.say("Sorry, I didn’t catch that. Please tell me the reason again.")
        response.redirect(f'/handle_reason?aid={appointment_id}')

    return Response(str(response), mimetype='text/xml')


@app.route('/')
def home():
    return "✅ AI Call Agent Running Successfully!"


@app.route('/debug')
def debug():
    """Shows all available routes."""
    return {
        "status": "running",
        "routes": [str(rule) for rule in app.url_map.iter_rules()]
    }


# ---------------- RUN APP ---------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
