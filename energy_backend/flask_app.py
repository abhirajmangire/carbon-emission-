from __future__ import annotations

from flask import Flask, jsonify, request
import os
from secrets import token_urlsafe
from flask_cors import CORS

from app.schemas import BillCreate
from app.services.calculations import (
    analyze_trends,
    build_summary,
    current_month_report,
    generate_advice,
    get_recent_usage,
    predict_usage,
)
from app.storage import storage
from app.settings import settings


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app, resources={r"*": {"origins": settings.cors_allow_origins}})
    issued_tokens: set[str] = set()
    otp_store: dict[str, str] = {}

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    # Auth (demo): accepts any non-empty username/password and returns a bearer token
    @app.post("/auth/login")
    def login():
        data = request.get_json(force=True, silent=True) or {}
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        if not username or not password:
            return jsonify({"detail": "username and password required"}), 400
        token = token_urlsafe(24)
        issued_tokens.add(token)
        return jsonify({"access_token": token, "token_type": "bearer"})

    @app.post("/auth/request-otp")
    def request_otp():
        data = request.get_json(force=True, silent=True) or {}
        contact = (data.get("contact") or "").strip()  # email or mobile
        if not contact:
            return jsonify({"detail": "contact required"}), 400
        otp = str(int.from_bytes(os.urandom(2), 'big') % 1000000).zfill(6)
        otp_store[contact] = otp
        # In real life, send via email/SMS. Here we return it for demo/testing.
        return jsonify({"sent": True, "otp_demo": otp})

    @app.post("/auth/verify-otp")
    def verify_otp():
        data = request.get_json(force=True, silent=True) or {}
        contact = (data.get("contact") or "").strip()
        otp = (data.get("otp") or "").strip()
        if not contact or not otp:
            return jsonify({"detail": "contact and otp required"}), 400
        if otp_store.get(contact) != otp:
            return jsonify({"detail": "invalid otp"}), 400
        # successful, issue token
        token = token_urlsafe(24)
        issued_tokens.add(token)
        # cleanup
        try:
            del otp_store[contact]
        except Exception:
            pass
        return jsonify({"access_token": token, "token_type": "bearer"})

    # Bills
    @app.post("/api/v1/bills/")
    def create_bill():
        # Auth check: require Bearer token
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth.split(" ", 1)[1] not in issued_tokens:
            return jsonify({"detail": "Unauthorized"}), 401
        data = request.get_json(force=True, silent=True) or {}
        try:
            bill = BillCreate(**data)
        except Exception as exc:  # pydantic validation error
            return jsonify({"detail": str(exc)}), 400
        if storage.find_bill(bill.year, bill.month) is not None:
            return jsonify({"detail": "Bill for this month already exists"}), 400
        created = storage.add_bill(bill)
        return jsonify(created.model_dump())

    @app.get("/api/v1/bills/")
    def list_bills():
        return jsonify([b.model_dump() for b in storage.list_bills()])

    # Usage
    @app.get("/api/v1/usage/recent")
    def recent_usage():
        limit = int(request.args.get("limit", 6))
        pts = get_recent_usage(limit)
        return jsonify([p.model_dump() for p in pts])

    # Summary
    @app.get("/api/v1/summary/")
    def summary():
        return jsonify(build_summary().model_dump())

    # Current month
    @app.get("/api/v1/current-month/")
    def current_month():
        report = current_month_report()
        if report is None:
            return jsonify({"detail": "No bills available"}), 404
        return jsonify(report.model_dump())

    # Analysis
    @app.get("/api/v1/analysis/trends")
    def trends():
        return jsonify(analyze_trends().model_dump())

    @app.get("/api/v1/analysis/predict")
    def predict():
        horizon = int(request.args.get("horizon_months", 3))
        return jsonify(predict_usage(horizon).model_dump())

    @app.get("/api/v1/analysis/averages")
    def averages():
        # last month values and 6-month averages
        from app.services.calculations import get_usage_points
        pts = get_usage_points()
        pts.sort(key=lambda p: (p.year, p.month))
        last = pts[-1] if pts else None
        last_month = {
            "kwh": (last.kilowatt_hours if last else 0.0),
            "emissions_kg": (last.emissions_kg if last else 0.0),
        }
        last6 = pts[-6:] if pts else []
        n = len(last6) if last6 else 0
        six_month_avg = {
            "kwh": (sum(p.kilowatt_hours for p in last6) / n if n else 0.0),
            "emissions_kg": (sum(p.emissions_kg for p in last6) / n if n else 0.0),
        }
        return jsonify({"last_month": last_month, "six_month_avg": six_month_avg})

    @app.post("/api/v1/tools/estimate-factor")
    def estimate_factor():
        """Estimate emission factor (kg CO2e/kWh) from cost and usage using a simple model.

        Assumptions:
        - total_cost ≈ (energy_price_per_kwh * kwh) + (carbon_price_per_kg * emission_factor * kwh)
        => emission_factor ≈ max(0, (total_cost/kwh - energy_price_per_kwh) / carbon_price_per_kg)

        Inputs JSON:
        - total_cost (float, required)
        - kwh (float, required)
        - energy_price_per_kwh (float, optional, default 0.10)
        - carbon_price_per_kg (float, optional, default 0.05)
        """
        data = request.get_json(force=True, silent=True) or {}
        try:
            total_cost = float(data.get("total_cost"))
            kwh = float(data.get("kwh"))
        except Exception:
            return jsonify({"detail": "total_cost and kwh required"}), 400
        if kwh <= 0:
            return jsonify({"detail": "kwh must be > 0"}), 400
        energy_price_per_kwh = float(data.get("energy_price_per_kwh", 0.10))
        carbon_price_per_kg = float(data.get("carbon_price_per_kg", 0.05))
        if carbon_price_per_kg <= 0:
            return jsonify({"detail": "carbon_price_per_kg must be > 0"}), 400
        cost_per_kwh = total_cost / kwh
        raw = (cost_per_kwh - energy_price_per_kwh) / carbon_price_per_kg
        estimated_factor = max(0.0, raw)
        return jsonify({
            "estimated_emission_factor_kg_per_kwh": estimated_factor,
            "inputs": {
                "total_cost": total_cost,
                "kwh": kwh,
                "energy_price_per_kwh": energy_price_per_kwh,
                "carbon_price_per_kg": carbon_price_per_kg,
            },
            "notes": "Simple linear model; adjust assumptions to your region/pricing."
        })

    # Advice
    @app.get("/api/v1/advice/")
    def advice():
        return jsonify(generate_advice().model_dump())

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)

