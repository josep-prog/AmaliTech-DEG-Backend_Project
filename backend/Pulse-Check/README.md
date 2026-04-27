# Pulse-Check Device Heartbeat Monitor

A lightweight REST API that monitors remote devices by tracking heartbeat signals. If a device stops sending signals within its defined timeout window, the system automatically flags it as down.

## Tech Stack

- Python 3
- Flask 3.0
- APScheduler 3.10

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

The server starts on `http://localhost:5000` by default.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Check if the server is running |
| `POST` | `/monitors` | Register a new device monitor |
| `POST` | `/monitors/{id}/heartbeat` | Send a heartbeat for a device |
| `POST` | `/monitors/{id}/pause` | Pause monitoring for a device |
| `DELETE` | `/monitors/{id}` | Remove a monitor |
| `GET` | `/monitors` | List all monitors |
| `GET` | `/monitors/{id}` | Get a specific monitor |
| `GET` | `/monitors/{id}/heartbeat-history` | View heartbeat history for a device |

### Register a monitor

```json
POST /monitors
{
  "id": "device-123",
  "timeout": 30,
  "alert_email": "admin@example.com"
}
```

---

## How It Works

### User Story 1: Registering a Monitor

Devices are registered via `POST /monitors` with a device ID, timeout (in seconds), and an alert email. The system validates the input, stores the monitor, and immediately starts a background timer. If no heartbeat arrives before the timer runs out, the device gets marked as down.

<img width="800" height="600" alt="f1" src="https://github.com/user-attachments/assets/3fda6169-ba26-459b-8b77-bfefcc7820ce" />

---

### User Story 2: Heartbeat (Timer Reset)

Devices send a heartbeat via `POST /monitors/{id}/heartbeat`. Each heartbeat resets the timer back to the full timeout and logs the timestamp. The response confirms the reset and shows how many seconds remain until the next expected heartbeat.

<img width="800" height="600" alt="f2" src="https://github.com/user-attachments/assets/959d19b5-faa7-41b1-b817-cf889185b0eb" />

---

### User Story 3: Alert on Failure

If the timer expires without receiving a heartbeat, the device status changes to `"down"` and an alert is logged:

```json
{ "ALERT": "Device device-123 is down!", "time": 1234567890.0 }
```

In a real deployment, this would connect to an email service or external monitoring dashboard.

<img width="800" height="600" alt="f3" src="https://github.com/user-attachments/assets/a8606100-5aa0-43ac-8bd2-9dc5618f458b" />

---

### Bonus: Pause / Snooze

`POST /monitors/{id}/pause` puts a device in maintenance mode — the timer stops and no alerts fire. When a heartbeat comes in after a pause, the device automatically resumes active monitoring and the timer restarts.

<img width="800" height="600" alt="f4" src="https://github.com/user-attachments/assets/a8606100-5aa0-43ac-8bd2-9dc5618f458b" />

---

### Extra Feature: Heartbeat History

Every heartbeat timestamp is stored per device, capped at the 50 most recent entries. This makes it easier to see how often a device has been communicating and spot any gaps in activity.

<img width="800" height="600" alt="f5" src="https://github.com/user-attachments/assets/cb0a4d91-44c2-4944-90f4-5928f29ee6ea" />
