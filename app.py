from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import openai, os, sqlite3

# ---------------- APP CONFIG ---------------- #
app = Flask(__name__)

# Load API keys from environment variables (configured in Render)
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
@app.route("/voice", methods=['POST'])
def voice():
    """Handle incoming calls and ask for the user's name."""
    response = VoiceResponse()
    gather = Gather(input='speech', action='/handle_name', method='POST')
    gather.say("Hello! This is your AI assistant. Please tell me your name to book an appointment.")
    response.append(gather)
    response.redirect('/voice')  # repeat if no input
    return Response(str(response), mimetype='text/xml')

@app.route("/handle_name", methods=['POST'])
def handle_name():
    """Capture name and ask for appointment date."""
    name = request.form.get('SpeechResult', '').strip()
    response = VoiceResponse()

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

@app.route("/handle_date", methods=['POST'])
def handle_date():
    """Capture date and ask for time."""
    date = request.form.get('SpeechResult', '').strip()
    appointment_id = request.args.get('aid')
    response = VoiceResponse()

    if date and appointment_id:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE appointments SET date = ? WHERE id = ?", (date, appointment_id))
        conn.commit()
        conn.close()

        gather = Gather(input='speech', action=f'/handle_time?aid={appointment_id}', method='POST')
        gather.say(f"Got it. What time on {date} would you prefer?")
        response.append(gather)
    else:
        response.say("Sorry, could you please repeat the date?")
        response.redirect(f'/handle_date?aid={appointment_id}')

    return Response(str(response), mimetype='text/xml')

@app.route("/handle_time", methods=['POST'])
def handle_time():
    """Capture time and ask for reason."""
    time = request.form.get('SpeechResult', '').strip()
    appointment_id = request.args.get('aid')
    response = VoiceResponse()

    if time and appointment_id:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE appointments SET time = ? WHERE id = ?", (time, appointment_id))
        conn.commit()
        conn.close()

        gather = Gather(input='speech', action=f'/handle_reason?aid={appointment_id}', method='POST')
        gather.say(f"Okay, {time} works. Could you please tell me the reason for your appointment?")
        response.append(gather)
    else:
        response.say("Sorry, please say the time again.")
        response.redirect(f'/handle_time?aid={appointment_id}')

    return Response(str(response), mimetype='text/xml')

@app.route("/handle_reason", methods=['POST'])
def handle_reason():
    """Capture reason and confirm appointment."""
    reason = request.form.get('SpeechResult', '').strip()
    appointment_id = request.args.get('aid')
    response = VoiceResponse()

    if reason and appointment_id:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE appointments SET reason = ? WHERE id = ?", (reason, appointment_id))
        conn.commit()

        c.execute("SELECT name, date, time FROM appointments WHERE id = ?", (appointment_id,))
        record = c.fetchone()
        conn.close()

        if record:
            name, date, time = record
            response.say(f"Thank you {name}. Your appointment has been booked on {date} at {time} for {reason}. Have a great day!")
        else:
            response.say("Sorry, there was a problem confirming your appointment.")
    else:
        response.say("Sorry, could you repeat the reason again?")
        response.redirect(f'/handle_reason?aid={appointment_id}')

    return Response(str(response), mimetype='text/xml')

@app.route('/')
def home():
    return "✅ AI Call Agent Running Successfully!"

# ---------------- RUN APP ---------------- #
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
