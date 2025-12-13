"""
Weather notification scheduler.

Scheduled pipeline:
- Fetch today's IoT/Sheets data (first N rows for today).
- Aggregate metrics (mean/median).
- Determine AQI level.
- Generate multilingual recommendations via GroqWeatherService.
- Send to users via WhatsApp (only with phone + consent).

Cron defaults:
- 06:00 Asia/Jakarta (morning routine)
- 12:00 Asia/Jakarta (only sends if AQI is unhealthy/hazardous)
"""
from __future__ import annotations

import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from pytz import timezone
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.user import User
from app.db.postgres import get_db
from app.services.weather.recommendation_service import WeatherRecommendationService
from app.services.weather.spreadsheet_service import SpreadsheetService
from app.services.whatsapp.wa_client import WAClient


class WeatherNotificationScheduler:
    """APScheduler-backed job runner for WA recommendations."""

    def __init__(
        self,
        tz: str = "Asia/Jakarta",
        spreadsheet_id: Optional[str] = None,
        worksheet_name: str = "Sheet1",
        max_rows_per_day: int = 20,
    ):
        self.tz = timezone(tz)
        self.scheduler = BackgroundScheduler(timezone=self.tz)
        self.spreadsheet_id = spreadsheet_id or get_settings().google_sheets_id
        self.worksheet_name = worksheet_name
        self.max_rows_per_day = max_rows_per_day

        self.sheet_service = SpreadsheetService()
        self.wa_client = WAClient()

    def start(self):
        """Start cron jobs."""
        # 06:00 WIB daily
        self.scheduler.add_job(self.run_morning_job, "cron", hour=6, minute=0, id="weather_morning")
        # 12:00 WIB daily (conditional send if AQI is bad)
        self.scheduler.add_job(self.run_midday_job, "cron", hour=12, minute=0, id="weather_midday")
        self.scheduler.start()

    def shutdown(self):
        """Gracefully stop scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    # Job entrypoints
    def run_morning_job(self):
        self._run_notifications(label="morning", force_send=True)

    def run_midday_job(self):
        self._run_notifications(label="midday", force_send=False)

    # Core pipeline
    def _run_notifications(self, label: str, force_send: bool):
        session = next(get_db())
        try:
            weather_data, aqi_level = self._fetch_today_weather()
            if not weather_data:
                print(f"[scheduler:{label}] No weather data for today.")
                return

            if not force_send and aqi_level not in {"unhealthy", "hazardous"}:
                print(f"[scheduler:{label}] AQI '{aqi_level}' not high enough, skipping midday send.")
                return

            users = self._eligible_users(session)
            if not users:
                print(f"[scheduler:{label}] No eligible users with consent + phone.")
                return

            recommendation_service = WeatherRecommendationService(session)
            sent = 0
            skipped = 0

            for user in users:
                language = user.language.value if user.language else "en"
                try:
                    recommendation = recommendation_service.get_personalized_recommendation(
                        user=user,
                        weather_data=weather_data,
                        google_sheets_id=self.spreadsheet_id,
                        google_sheets_worksheet=self.worksheet_name,
                    )
                except Exception as exc:  # noqa: BLE001
                    skipped += 1
                    print(f"[scheduler:{label}] Recommendation failed for user {user.id}: {exc}")
                    continue

                success = self.wa_client.send_recommendation(
                    phone_number=user.phone_e164.strip(),
                    recommendation=recommendation,
                    language=language,
                )
                if success:
                    sent += 1
                else:
                    skipped += 1

            print(f"[scheduler:{label}] Done. Sent={sent}, Skipped={skipped}, AQI={aqi_level}")
        finally:
            session.close()

    def _eligible_users(self, session: Session) -> List[User]:
        """Users with phone + consent."""
        return (
            session.query(User)
            .filter(
                User.phone_e164.isnot(None),
                User.phone_e164 != "",
                User.privacy_consent.is_(True),
            )
            .all()
        )

    def _fetch_today_weather(self) -> tuple[Optional[Dict[str, Any]], str]:
        """Fetch today's rows from Google Sheets and aggregate."""
        try:
            raw_rows = self.sheet_service.read_from_google_sheets(
                spreadsheet_id=self.spreadsheet_id,
                worksheet_name=self.worksheet_name,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[scheduler] Failed to fetch sheets data: {exc}")
            return None, "unknown"

        today_rows = self._filter_today_rows(raw_rows)
        if not today_rows:
            return None, "unknown"

        limited_rows = today_rows[: self.max_rows_per_day]
        aggregates = self._aggregate_rows(limited_rows)
        aqi_level = self._categorize_aqi(aggregates)

        aggregates["aqi_level"] = aqi_level
        return aggregates, aqi_level

    def _filter_today_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep rows whose timestamp is today in target timezone."""
        today_local = datetime.now(self.tz).date()
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            ts_raw = row.get("Timestamp") or row.get("timestamp") or row.get("Date") or row.get("date")
            ts = self._parse_timestamp(ts_raw)
            if ts and self._as_local(ts).date() == today_local:
                filtered.append(row)
        return filtered

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                return datetime.strptime(str(value), fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    def _as_local(self, ts: datetime) -> datetime:
        if ts.tzinfo is None:
            return self.tz.localize(ts)
        return ts.astimezone(self.tz)

    def _aggregate_rows(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute mean/median for selected pollutants."""
        metrics = {
            "pm25": [],
            "pm10": [],
            "co2": [],
            "co": [],
            "temperature": [],
            "humidity": [],
        }

        for row in rows:
            self._collect(metrics["pm25"], row, ["PM2.5 density", "PM2.5", "pm25", "PM25"])
            self._collect(metrics["pm10"], row, ["PM10 density", "PM10", "pm10"])
            self._collect(metrics["co2"], row, ["CO2", "co2"])
            self._collect(metrics["co"], row, ["CO", "co"])
            self._collect(metrics["temperature"], row, ["Temperature", "temperature", "Temp", "temp", "Suhu", "suhu"])
            self._collect(metrics["humidity"], row, ["Humidity", "humidity", "Hum", "hum", "Kelembaban", "kelembaban"])

        def agg(values: List[float]) -> Dict[str, Any]:
            if not values:
                return {"mean": None, "median": None}
            return {"mean": round(statistics.mean(values), 2), "median": round(statistics.median(values), 2)}

        aggregated = {
            "pm25_mean": agg(metrics["pm25"])["mean"],
            "pm25_median": agg(metrics["pm25"])["median"],
            "pm10_mean": agg(metrics["pm10"])["mean"],
            "pm10_median": agg(metrics["pm10"])["median"],
            "co2_mean": agg(metrics["co2"])["mean"],
            "co_mean": agg(metrics["co"])["mean"],
            "temperature_mean": agg(metrics["temperature"])["mean"],
            "humidity_mean": agg(metrics["humidity"])["mean"],
            "location": rows[0].get("Location") or rows[0].get("location") or "Bandung",
            "timestamp": datetime.now(self.tz).isoformat(),
        }

        # Backward-compatible aliases expected by GroqWeatherService
        aggregated["pm25"] = aggregated["pm25_mean"]
        aggregated["pm10"] = aggregated["pm10_mean"]
        aggregated["co"] = aggregated["co_mean"]
        aggregated["humidity"] = aggregated["humidity_mean"]
        aggregated["temperature"] = aggregated["temperature_mean"]
        return aggregated

    @staticmethod
    def _collect(bucket: List[float], row: Dict[str, Any], keys: List[str]):
        for key in keys:
            if key in row and row[key] not in (None, ""):
                try:
                    bucket.append(float(str(row[key]).replace(",", ".").strip()))
                    return
                except ValueError:
                    continue

    @staticmethod
    def _categorize_aqi(aggregates: Dict[str, Any]) -> str:
        pm25 = aggregates.get("pm25") or 0
        pm10 = aggregates.get("pm10") or 0

        if pm25 is None and pm10 is None:
            return "unknown"

        if (pm25 and pm25 > 75) or (pm10 and pm10 > 100):
            return "hazardous"
        if (pm25 and pm25 > 35) or (pm10 and pm10 > 75):
            return "unhealthy"
        if (pm25 and pm25 > 12) or (pm10 and pm10 > 50):
            return "moderate"
        return "good"


def start_default_scheduler() -> WeatherNotificationScheduler:
    """Helper to start scheduler with defaults."""
    scheduler = WeatherNotificationScheduler()
    scheduler.start()
    return scheduler

