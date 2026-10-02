# Food ordering routes, registered by server.py under /food.
#
#   order page:  http://<this PC's IP>:5000/food/
#   queue page:  http://localhost:5000/food/queue
#   queue API:   GET /food/orders, POST /food/orders, POST /food/orders/<id>/complete
#
# The ThingsBoard queue widget (queue_widget.html) polls GET /food/orders.

import json
import os
import threading
from datetime import datetime

from flask import Blueprint, jsonify, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
ORDERS_FILE = os.path.join(HERE, "orders.json")   # survives restarts

bp = Blueprint("food_ordering", __name__)

lock = threading.Lock()   # Flask serves requests on several threads


# ---------- Storage ----------

def load():
    if not os.path.exists(ORDERS_FILE):
        return {"last_number": 0, "queue": [], "completed": []}
    with open(ORDERS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save(data):
    tmp = ORDERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, ORDERS_FILE)   # never leave a half-written file behind


def clean_names(value):
    if not isinstance(value, list):
        return []
    return [str(name).strip() for name in value if str(name).strip()]


# ---------- Orders API ----------

@bp.route("/orders", methods=["POST"])
def place_order():
    body = request.get_json(silent=True) or {}
    snacks = clean_names(body.get("snacks"))
    drinks = clean_names(body.get("drinks"))
    office = str(body.get("office", "")).strip()

    if not snacks and not drinks:
        return jsonify({"error": "Order has no items"}), 400
    if not office:
        return jsonify({"error": "Order has no delivery location"}), 400

    with lock:
        data = load()
        data["last_number"] += 1
        order = {
            "id": f"ORD-{data['last_number']:04d}",
            "placed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "snacks": snacks,
            "drinks": drinks,
            "office": office,
        }
        data["queue"].append(order)
        save(data)

    print(f"New order {order['id']} for {office}")
    return jsonify(order), 201


@bp.route("/orders", methods=["GET"])
def list_orders():
    # Queued orders, oldest first
    with lock:
        return jsonify(load()["queue"])


@bp.route("/orders/<order_id>/complete", methods=["POST"])
def complete_order(order_id):
    with lock:
        data = load()
        order = next((o for o in data["queue"] if o["id"] == order_id), None)
        if order is None:
            return jsonify({"error": f"Order {order_id} is not in the queue"}), 404
        data["queue"].remove(order)
        order["completed_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        data["completed"].append(order)   # kept as a history, not shown in the queue
        save(data)

    print(f"Order {order_id} completed")
    return jsonify(order)


# ---------- Pages ----------

@bp.route("/")
def order_page():
    return send_from_directory(HERE, "index.html")


@bp.route("/queue")
def queue_page():
    # Same markup as the ThingsBoard widget, for checking the queue in a browser
    return send_from_directory(HERE, "queue_widget.html")


@bp.route("/<folder>/<path:filename>")
def product_images(folder, filename):
    if folder not in ("Vending_Machine", "Coffee_Machine"):
        return "Not found", 404
    return send_from_directory(os.path.join(HERE, folder), filename)
