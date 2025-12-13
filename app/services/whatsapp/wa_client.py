"""Thin WhatsApp client wrapper to send structured recommendations."""
from typing import Dict, Any

from app.services.notification.whatsapp_service import WhatsAppService


class WAClient:
    """Wrapper around WhatsAppService for recommendation payloads."""

    def __init__(self):
        self.service = WhatsAppService()

    def send_recommendation(self, phone_number: str, recommendation: Dict[str, Any], language: str) -> bool:
        """
        Send a recommendation message via WhatsApp.

        Args:
            phone_number: E.164 formatted number
            recommendation: structured payload from GroqWeatherService
            language: user-preferred language
        """
        return self.service.send_weather_warning_instant(
            phone_number=phone_number,
            recommendation=recommendation,
            language=language or "en",
        )



