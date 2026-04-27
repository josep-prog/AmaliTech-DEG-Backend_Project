import atexit
import json
from datetime import datetime, timedelta, timezone
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, request

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))

monitors = {}
lock = Lock()

MAX_HEARTBEAT_HISTORY = 50
MAX_TIMEOUT = 86400  # 24 hours


def is_valid_email(email):
    parts = email.split("@")
    return len(parts) == 2 and "." in parts[1]


def fire_alert(device_id):
    with lock:
        mon = monitors.get(device_id)
        if not mon or mon["status"] != "active":
            return
        mon["status"] = "down"
        mon["alert_count"] += 1
    print(json.dumps({"ALERT": f"Device {device_id} is down!", "time": datetime.now(timezone.utc).isoformat()}), flush=True)


def schedule_alert(device_id, timeout):
    run_date = datetime.now(timezone.utc) + timedelta(seconds=timeout)
    scheduler.add_job(
        fire_alert,
        trigger="date",
        run_date=run_date,
        id=f"monitor_{device_id}",
        args=[device_id],
        replace_existing=True,
    )
    return run_date


def cancel_alert(device_id):
    try:
        scheduler.remove_job(f"monitor_{device_id}")
    except Exception:
        pass


@app.get("/health")
def health_check():
    return jsonify({"status": "ok", "monitors": len(monitors)})


@app.post("/monitors")
def create_monitor():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "expected JSON body"}), 400

    device_id = data.get("id")
    timeout = data.get("timeout")
    alert_email = data.get("alert_email")

    if not device_id or timeout is None or not alert_email:
        return jsonify({"error": "id, timeout, and alert_email are all required"}), 400

    if not is_valid_email(str(alert_email)):
        return jsonify({"error": "alert_email must be a valid email address"}), 400

    try:
        timeout = int(timeout)
        if timeout <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "timeout must be a positive integer"}), 400

    if timeout > MAX_TIMEOUT:
        return jsonify({"error": f"timeout cannot exceed {MAX_TIMEOUT} seconds (24 hours)"}), 400

    with lock:
        if device_id in monitors:
            return jsonify({"error": f"monitor '{device_id}' already exists; delete it first"}), 409

        run_date = schedule_alert(device_id, timeout)
        monitors[device_id] = {
            "id": device_id,
            "timeout": timeout,
            "alert_email": alert_email,
            "status": "active",
            "alert_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat_at": None,
            "next_alert_at": run_date.isoformat(),
            "heartbeat_history": [],
        }

    return jsonify({"message": f"monitor '{device_id}' registered, timeout is {timeout}s"}), 201


@app.post("/monitors/<device_id>/heartbeat")
def heartbeat(device_id):
    with lock:
        mon = monitors.get(device_id)
        if not mon:
            return jsonify({"error": f"no monitor found for '{device_id}'"}), 404

        if mon["status"] == "down":
            return jsonify({"error": f"monitor '{device_id}' is down; delete and re-register it"}), 409

        was_paused = mon["status"] == "paused"
        now = datetime.now(timezone.utc).isoformat()

        mon["heartbeat_history"].append(now)
        mon["heartbeat_history"] = mon["heartbeat_history"][-MAX_HEARTBEAT_HISTORY:]
        mon["last_heartbeat_at"] = now
        mon["status"] = "active"

        run_date = schedule_alert(device_id, mon["timeout"])
        mon["next_alert_at"] = run_date.isoformat()

    msg = f"heartbeat ok, timer reset to {mon['timeout']}s"
    if was_paused:
        msg = f"monitor auto-unpaused; {msg}"
    return jsonify({"message": msg})


@app.post("/monitors/<device_id>/pause")
def pause_monitor(device_id):
    with lock:
        mon = monitors.get(device_id)
        if not mon:
            return jsonify({"error": f"no monitor found for '{device_id}'"}), 404
        if mon["status"] == "down":
            return jsonify({"error": f"monitor '{device_id}' is already down; cannot pause"}), 409
        if mon["status"] == "paused":
            return jsonify({"message": "already paused"})

        cancel_alert(device_id)
        mon["status"] = "paused"
        mon["next_alert_at"] = None

    return jsonify({"message": f"monitor '{device_id}' paused"})


@app.delete("/monitors/<device_id>")
def delete_monitor(device_id):
    with lock:
        mon = monitors.pop(device_id, None)
        if not mon:
            return jsonify({"error": f"no monitor found for '{device_id}'"}), 404
        cancel_alert(device_id)

    return jsonify({"message": f"monitor '{device_id}' deleted"})


@app.get("/monitors")
def list_monitors():
    status_filter = request.args.get("status")
    with lock:
        result = list(monitors.values())
    if status_filter:
        result = [m for m in result if m["status"] == status_filter]
    return jsonify(result)


@app.get("/monitors/<device_id>")
def get_monitor(device_id):
    with lock:
        mon = monitors.get(device_id)
        if not mon:
            return jsonify({"error": f"no monitor found for '{device_id}'"}), 404
        return jsonify(mon)


@app.get("/monitors/<device_id>/heartbeat-history")
def heartbeat_history(device_id):
    with lock:
        mon = monitors.get(device_id)
        if not mon:
            return jsonify({"error": f"no monitor found for '{device_id}'"}), 404
        return jsonify({"device_id": device_id, "heartbeat_history": mon["heartbeat_history"]})


if __name__ == "__main__":
    app.run(debug=False)
