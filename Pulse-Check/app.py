import atexit
import json
from datetime import datetime, timedelta, timezone
from threading import Lock

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, request

app = Flask(__name__)

monitors = {}
lock = Lock()

scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))


def is_valid_email(email):
    parts = email.split("@")
    return len(parts) == 2 and "." in parts[1]


def fire_alert(device_id):
    with lock:
        mon = monitors.get(device_id)
        if mon is None or mon["status"] != "active":
            return
        mon["status"] = "down"
        mon["alert_count"] += 1
    # log to stdout for now
    print(f"ALERT: device {device_id} is down at {datetime.utcnow().isoformat()}", flush=True)


def schedule_alert(device_id, timeout):
    run_date = datetime.now(timezone.utc) + timedelta(seconds=timeout)
    scheduler.add_job(
        fire_alert,
        "date",
        run_date=run_date,
        id=f"monitor_{device_id}",
        args=[device_id],
        replace_existing=True,
    )
    return run_date


def cancel_alert(device_id):
    try:
        scheduler.remove_job(f"monitor_{device_id}")
    except:
        pass


@app.get("/health")
def health_check():
    return jsonify({"status": "ok", "monitors": len(monitors)})


@app.post("/monitors")
def create_monitor():
    data = request.get_json()
    if data is None:
        return jsonify({"error": "request body must be JSON"}), 400

    device_id = data.get("id")
    timeout = data.get("timeout")
    alert_email = data.get("alert_email")

    if not device_id or timeout is None or not alert_email:
        return jsonify({"error": "id, timeout, and alert_email are required"}), 400

    if not is_valid_email(str(alert_email)):
        return jsonify({"error": "alert_email is not a valid email"}), 400

    try:
        timeout = int(timeout)
        if timeout <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "timeout must be a positive integer"}), 400

    if timeout > 86400:  # 24 hours max
        return jsonify({"error": "timeout cannot exceed 86400 seconds"}), 400

    with lock:
        if device_id in monitors:
            return jsonify({"error": f"a monitor with id '{device_id}' already exists"}), 409

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
        if mon is None:
            return jsonify({"error": f"no monitor found for '{device_id}'"}), 404

        if mon["status"] == "down":
            return jsonify({"error": f"monitor '{device_id}' is down; delete and re-register it"}), 409

        was_paused = mon["status"] == "paused"
        now = datetime.now(timezone.utc).isoformat()

        mon["heartbeat_history"].append(now)
        if len(mon["heartbeat_history"]) > 50:
            mon["heartbeat_history"] = mon["heartbeat_history"][-50:]
        mon["last_heartbeat_at"] = now
        mon["status"] = "active"

        run_date = schedule_alert(device_id, mon["timeout"])
        mon["next_alert_at"] = run_date.isoformat()

    msg = f"heartbeat ok, timer reset to {mon['timeout']}s"
    if was_paused:
        msg = "monitor auto-unpaused; " + msg
    return jsonify({"message": msg})


@app.post("/monitors/<device_id>/pause")
def pause_monitor(device_id):
    with lock:
        mon = monitors.get(device_id)
        if mon == None:
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
        if mon == None:
            return jsonify({"error": f"no monitor found for '{device_id}'"}), 404
        cancel_alert(device_id)

    return jsonify({"message": f"monitor '{device_id}' deleted"})


@app.get("/monitors")
def list_monitors():
    status_filter = request.args.get("status")
    with lock:
        result = list(monitors.values())
    if status_filter:
        filtered = []
        for m in result:
            if m["status"] == status_filter:
                filtered.append(m)
        return jsonify(filtered)
    return jsonify(result)


@app.get("/monitors/<device_id>")
def get_monitor(device_id):
    with lock:
        mon = monitors.get(device_id)
        if mon is None:
            return jsonify({"error": f"no monitor found for '{device_id}'"}), 404
        return jsonify(mon)


@app.get("/monitors/<device_id>/heartbeat-history")
def heartbeat_history(device_id):
    with lock:
        mon = monitors.get(device_id)
        if mon == None:
            return jsonify({"error": f"no monitor found for '{device_id}'"}), 404
        return jsonify({"device_id": device_id, "heartbeat_history": mon["heartbeat_history"]})


if __name__ == "__main__":
    app.run(debug=False)
