import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


LANGUAGE_TASKS: Dict[str, Dict[str, str]] = {
    "id": {
        "task": (
            "TUGAS:\n"
            "Berikan ringkasan kualitas udara hari ini dan rekomendasi aksi. "
            "Fokus pada mitigasi kesehatan, aktivitas luar ruang, ventilasi, dan masker. "
            "Gunakan Bahasa Indonesia yang ringkas dan tegas."
        ),
        "style": "Gunakan nada informatif, langsung ke poin, hindari basa-basi.",
    },
    "en": {
        "task": (
            "TASK:\n"
            "Provide today's air quality summary and action recommendations. "
            "Focus on health mitigation, outdoor activity limits, ventilation, and masks. "
            "Use concise, direct English."
        ),
        "style": "Tone: informative, succinct, actionable.",
    },
    "su": {
        "task": (
            "TUGAS:\n"
            "Jelaskeun kualitas udara ayeuna jeung saran aksi. "
            "Fokus kana kaséhatan, aktivitas luar, ventilasi, jeung masker. "
            "Pake basa Sunda basajan, singkat."
        ),
        "style": "Nada ramah tapi langsung.",
    },
}


class GroqWeatherService:
    """Generate multilingual, structured weather recommendations using Groq LLM."""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment variables")

        self.client = Groq(api_key=api_key)
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"

    def generate_recommendation(
        self,
        weather_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        context_knowledge: List[str],
        language: str = "id",
        use_streaming: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate structured, language-aware air-quality guidance.

        Output schema (stable):
        {
          "aqi_level": "good|moderate|unhealthy|hazardous",
          "summary": "<string>",
          "recommendation": "<string>",
          "tips": ["<string>", "<string>"]
        }
        """
        lang = language if language in LANGUAGE_TASKS else "en"

        messages = [
            {"role": "system", "content": self._build_system_prompt(lang)},
            {"role": "user", "content": self._build_user_prompt(weather_data, user_profile, context_knowledge, lang)},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
                max_tokens=1200,
                top_p=0.9,
                stream=use_streaming,
                response_format={"type": "json_object"},
            )

            if use_streaming:
                return self._handle_streaming(response)

            content = response.choices[0].message.content
            return self._parse_response(content, lang)

        except (ValueError, KeyError, AttributeError) as e:
            return {
                "error": f"Error generating recommendation: {str(e)}",
                "aqi_level": "unknown",
                "summary": "",
                "recommendation": "",
                "tips": [],
                "raw_error": str(e),
            }
        except Exception as e:
            return {
                "error": f"Unexpected error: {str(e)}",
                "aqi_level": "unknown",
                "summary": "",
                "recommendation": "",
                "tips": [],
                "raw_error": str(e),
            }

    def _build_system_prompt(self, language: str) -> str:
        """
        Role + structured-output contract using Groq prompting patterns:
        - Role Prompting
        - Instruction Hierarchy
        - Structured Output
        - Context Blocks
        - Style Control
        """
        task = LANGUAGE_TASKS[language]["task"]
        style = LANGUAGE_TASKS[language]["style"]

        return f"""
[ROLE]
You are an environmental health specialist focused on West Java (Bandung/BMKG context). 
You speak the user's preferred language and always return STRICT JSON only.

[OUTPUT CONTRACT]
Return JSON exactly:
{{
  "aqi_level": "good|moderate|unhealthy|hazardous",
  "summary": "<concise overview of current air quality in target language>",
  "recommendation": "<one short paragraph, target language>",
  "tips": ["<short actionable tip 1>", "<tip 2>", "<tip 3>"]
}}

[RULES]
- Never add text outside JSON.
- Use the requested language for summary, recommendation, and tips.
- Be concise, actionable, and specific to today's data.
- If data is missing, be conservative and still output valid JSON.

[STYLE]
{style}

[TASK BASE]
{task}
"""

    def _build_user_prompt(
        self,
        weather_data: Dict[str, Any],
        user_profile: Dict[str, Any],
        context_knowledge: List[str],
        language: str,
    ) -> str:
        """Context block for the model."""
        thresholds = {
            "good": "PM2.5 <= 12, PM10 <= 50",
            "moderate": "PM2.5 12-35, PM10 50-75",
            "unhealthy": "PM2.5 35-75, PM10 75-100",
            "hazardous": "PM2.5 > 75 or PM10 > 100",
        }

        knowledge_context = ""
        if context_knowledge:
            knowledge_context = "\n".join(
                [f"- Context {i+1}: {knowledge}" for i, knowledge in enumerate(context_knowledge[:3])]
            )

        lang_label = {"id": "Bahasa Indonesia", "en": "English", "su": "Bahasa Sunda"}.get(language, "English")

        return f"""
[DATA SNAPSHOT]
- PM2.5: {weather_data.get('pm25', 'N/A')}
- PM10: {weather_data.get('pm10', 'N/A')}
- O3: {weather_data.get('o3', 'N/A')}
- NO2: {weather_data.get('no2', 'N/A')}
- SO2: {weather_data.get('so2', 'N/A')}
- CO/CO₂: {weather_data.get('co', weather_data.get('co2', 'N/A'))}
- Temperature: {weather_data.get('temperature', 'N/A')}
- Humidity: {weather_data.get('humidity', 'N/A')}
- Location: {weather_data.get('location', 'N/A')}
- Timestamp: {weather_data.get('timestamp', 'N/A')}

[USER PROFILE]
- Age: {user_profile.get('age', 'N/A')}
- Occupation: {user_profile.get('occupation', 'N/A')}
- Location: {user_profile.get('location', 'N/A')}
- Activity level: {user_profile.get('activity_level', 'N/A')}
- Sensitivity: {user_profile.get('sensitivity_level', 'N/A')}
- Health conditions: {user_profile.get('health_conditions', 'N/A')}

[INTERNAL THRESHOLDS]
- {thresholds['good']}
- {thresholds['moderate']}
- {thresholds['unhealthy']}
- {thresholds['hazardous']}

[LANGUAGE PREFERENCE]
- Target language: {lang_label}

[KNOWLEDGE CONTEXT]
{knowledge_context if knowledge_context else '- None'}
"""

    def _parse_response(self, content: str, language: str) -> Dict[str, Any]:
        """Parse JSON response from LLM and normalize fields."""
        def ensure_list(val: Any) -> List[Any]:
            if isinstance(val, list):
                return val
            if val is None:
                return []
            return [val]

        try:
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content.strip())
        except json.JSONDecodeError as e:
            return {
                "error": "Failed to parse response",
                "raw_content": content,
                "parse_error": str(e),
                "aqi_level": "unknown",
                "summary": "",
                "recommendation": "",
                "tips": [],
            }

        aqi_level = str(data.get("aqi_level", "unknown")).lower()
        if aqi_level not in {"good", "moderate", "unhealthy", "hazardous"}:
            aqi_level = "unknown"

        tips = ensure_list(data.get("tips"))

        normalized = {
            "aqi_level": aqi_level,
            "summary": data.get("summary", ""),
            "recommendation": data.get("recommendation", ""),
            "tips": [str(tip) for tip in tips if tip],
            # backwards-compatible keys for existing callers
            "risk_level": self._map_aqi_to_risk(aqi_level),
            "primary_concern": data.get("summary", ""),
            "personalized_advice": data.get("recommendation", ""),
        }
        return normalized

    @staticmethod
    def _map_aqi_to_risk(aqi_level: str) -> str:
        """Map new AQI levels to legacy risk labels."""
        mapping = {
            "good": "low",
            "moderate": "medium",
            "unhealthy": "high",
            "hazardous": "critical",
        }
        return mapping.get(aqi_level, "unknown")

    def _handle_streaming(self, stream):
        """Handle streaming response."""
        full_content = ""
        for chunk in stream:
            if chunk.choices[0].delta.content:
                full_content += chunk.choices[0].delta.content
        return self._parse_response(full_content, language="en")
