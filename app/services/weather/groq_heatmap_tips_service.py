"""
Groq Heatmap Tips Service
Service to generate AI tips for heatmap using Groq LLM
"""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, List

from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


# Bandung-specific context for tips
BANDUNG_CONTEXT = """
[KONTEKS WILAYAH BANDUNG]
- Bandung terletak di dataran tinggi dengan topografi cekungan
- Sering terjadi inversi suhu yang memerangkap polusi
- Aktivitas industri dan lalu lintas padat di pusat kota
- Polusi PM2.5 sering tinggi di pagi hari (06:00-09:00) dan sore (17:00-20:00)
- Kawasan Dago, Setiabudi, dan Cicaheum memiliki tingkat polusi berbeda
- Musim kemarau (Juni-September) biasanya lebih buruk
- Polusi cenderung lebih tinggi di pusat kota dibanding pinggiran
"""


class GroqHeatmapTipsService:
    """Service to generate AI tips for heatmap using Groq LLM."""

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment variables")

        self.client = Groq(api_key=api_key)
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"

    def generate_tips(
        self,
        pm25: Optional[float] = None,
        pm10: Optional[float] = None,
        air_quality: Optional[str] = None,
        risk_level: Optional[str] = None,
        location: Optional[str] = None,
        language: str = "id"
    ) -> Dict[str, Any]:
        # Build prompt for tips
        system_prompt = self._build_system_prompt(language)
        user_prompt = self._build_user_prompt(
            pm25, pm10, air_quality, risk_level, location, language
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1500,
                top_p=0.9,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            parsed = self._parse_response(content, language)
            return parsed

        except (ValueError, KeyError, AttributeError) as e:
            return self._get_fallback_tips(pm25, pm10, risk_level, language)
        except Exception as e:
            return self._get_fallback_tips(pm25, pm10, risk_level, language)

    def _build_system_prompt(self, language: str) -> str:
        prompts = {
            "id": """Anda adalah ahli kesehatan lingkungan dan kualitas udara yang berpengalaman.
Tugas Anda adalah memberikan penjelasan yang mudah dipahami dan tips praktis tentang polusi udara berdasarkan data PM2.5 dan PM10 untuk ditampilkan di heatmap dashboard.

Output JSON dengan format:
{
  "title": "Judul penjelasan",
  "explanation": "Penjelasan singkat tentang kondisi polusi udara saat ini",
  "tips": [
    {
      "title": "Kesehatan|Aktivitas|Perlindungan",
      "description": "Deskripsi singkat kategori tips",
      "items": ["Tips praktis 1", "Tips praktis 2", "Tips praktis 3"],
      "category": "Kesehatan|Aktivitas|Perlindungan",
      "priority": "high|medium|low"
    }
  ],
  "health_impact": "Dampak kesehatan yang mungkin terjadi",
  "prevention": "Cara pencegahan yang disarankan"
}

PENTING: Setiap item dalam array "tips" HARUS memiliki:
- "title": Judul kategori (wajib)
- "description": Deskripsi singkat (wajib)
- "items": Array of strings dengan tips praktis (wajib, minimal 2-3 items)
- "category": Sama dengan title (untuk backward compatibility)
- "priority": high|medium|low

Gunakan bahasa Indonesia yang mudah dipahami, informatif, dan actionable. Fokus pada tips yang relevan dengan tingkat polusi yang ditampilkan.""",
            "en": """You are an experienced environmental health and air quality expert.
Your task is to provide easy-to-understand explanations and practical tips about air pollution based on PM2.5 and PM10 data for display on a heatmap dashboard.

Output JSON with format:
{
  "title": "Explanation title",
  "explanation": "Brief explanation about current air pollution condition",
  "tips": [
    {
      "title": "Health|Activity|Protection",
      "description": "Brief description of tip category",
      "items": ["Practical tip 1", "Practical tip 2", "Practical tip 3"],
      "category": "Health|Activity|Protection",
      "priority": "high|medium|low"
    }
  ],
  "health_impact": "Possible health impacts",
  "prevention": "Recommended prevention methods"
}

IMPORTANT: Each item in "tips" array MUST have:
- "title": Category title (required)
- "description": Brief description (required)
- "items": Array of strings with practical tips (required, minimum 2-3 items)
- "category": Same as title (for backward compatibility)
- "priority": high|medium|low

Use easy-to-understand English, informative, and actionable. Focus on tips relevant to the pollution level displayed.""",
            "su": """Anjeun ahli kaséhatan lingkungan sareng kualitas udara anu berpengalaman.
Tugas anjeun nyaéta masihan penjelasan anu gampang dipahami sareng tips praktis ngeunaan polusi udara dumasar kana data PM2.5 sareng PM10 pikeun ditampilkeun dina heatmap dashboard.

Output JSON kalayan format:
{
  "title": "Judul penjelasan",
  "explanation": "Penjelasan singkat ngeunaan kaayaan polusi udara ayeuna",
  "tips": [
    {
      "title": "Kaséhatan|Aktivitas|Perlindungan",
      "description": "Deskripsi singkat kategori tips",
      "items": ["Tips praktis 1", "Tips praktis 2", "Tips praktis 3"],
      "category": "Kaséhatan|Aktivitas|Perlindungan",
      "priority": "high|medium|low"
    }
  ],
  "health_impact": "Dampak kaséhatan anu mungkin lumangsung",
  "prevention": "Cara pencegahan anu disarankeun"
}

PENTING: Unggal item dina array "tips" KEDAH gaduh:
- "title": Judul kategori (wajib)
- "description": Deskripsi singkat (wajib)
- "items": Array of strings kalayan tips praktis (wajib, minimal 2-3 items)
- "category": Sarua jeung title (pikeun backward compatibility)
- "priority": high|medium|low

Gunakeun basa Sunda anu gampang dipahami, informatif, sareng actionable. Fokus kana tips anu relevan sareng tingkat polusi anu ditampilkeun."""
        }
        return prompts.get(language, prompts["id"])

    def _build_user_prompt(
        self,
        pm25: Optional[float],
        pm10: Optional[float],
        air_quality: Optional[str],
        risk_level: Optional[str],
        location: Optional[str],
        language: str
    ) -> str:
        """Build user prompt with pollution data and Bandung context if relevant"""
        
        # Check if location is Bandung or West Java
        location_str = str(location).lower() if location else ""
        is_bandung = "bandung" in location_str or "jawa barat" in location_str or "west java" in location_str
        
        # Add Bandung context if relevant
        bandung_context = ""
        if is_bandung:
            bandung_context = BANDUNG_CONTEXT
        
        data_info = f"""
DATA KUALITAS UDARA:
- PM2.5: {pm25 if pm25 is not None else 'Tidak tersedia'} μg/m³
- PM10: {pm10 if pm10 is not None else 'Tidak tersedia'} μg/m³
- Status Kualitas Udara: {air_quality if air_quality else 'Tidak tersedia'}
- Level Risiko: {risk_level.upper() if risk_level else 'Tidak tersedia'}
- Lokasi: {location if location else 'Tidak tersedia'}
{bandung_context}
"""

        task_prompts = {
            "id": f"""Berdasarkan data di atas{' DAN konteks wilayah Bandung/Jawa Barat' if is_bandung else ''}, berikan:
1. Penjelasan singkat tentang kondisi polusi udara saat ini di lokasi tersebut{' (spesifik untuk Bandung)' if is_bandung else ''}
2. Tips praktis yang bisa dilakukan untuk melindungi kesehatan (3-5 tips) - {'sesuaikan dengan kondisi Bandung' if is_bandung else 'relevan dengan lokasi'}
3. Dampak kesehatan yang mungkin terjadi jika terpapar polusi ini
4. Cara pencegahan yang disarankan{' (spesifik untuk kondisi Bandung)' if is_bandung else ''}

Fokus pada tips yang actionable dan mudah dipahami oleh masyarakat umum{' di Bandung' if is_bandung else ''}. 
{'Sertakan referensi waktu-waktu tertentu di Bandung yang perlu dihindari jika relevan (misalnya jam sibuk 06:00-09:00 dan 17:00-20:00).' if is_bandung else ''}
Tips harus relevan dengan tingkat polusi yang ditampilkan.""",
            "en": f"""Based on the above data{' and Bandung/West Java context' if is_bandung else ''}, provide:
1. Brief explanation about current air pollution condition at this location{' (specific to Bandung)' if is_bandung else ''}
2. Practical tips that can be done to protect health (3-5 tips) - {'adjusted for Bandung conditions' if is_bandung else 'relevant to location'}
3. Possible health impacts if exposed to this pollution
4. Recommended prevention methods{' (specific to Bandung conditions)' if is_bandung else ''}

Focus on actionable tips that are easy to understand for the general public{' in Bandung' if is_bandung else ''}.
{'Include references to specific times in Bandung that should be avoided if relevant (e.g., rush hours 06:00-09:00 and 17:00-20:00).' if is_bandung else ''}
Tips must be relevant to the pollution level displayed.""",
            "su": f"""Dumasar kana data di luhur{' sareng konteks wilayah Bandung/Jawa Barat' if is_bandung else ''}, masihan:
1. Penjelasan singkat ngeunaan kaayaan polusi udara ayeuna di lokasi éta{' (spesifik pikeun Bandung)' if is_bandung else ''}
2. Tips praktis anu tiasa dilakukeun pikeun ngajaga kaséhatan (3-5 tips) - {'disesuaikeun sareng kaayaan Bandung' if is_bandung else 'relevan sareng lokasi'}
3. Dampak kaséhatan anu mungkin lumangsung upami kakeunaan polusi ieu
4. Cara pencegahan anu disarankeun{' (spesifik pikeun kaayaan Bandung)' if is_bandung else ''}

Fokus kana tips anu actionable sareng gampang dipahami ku masarakat umum{' di Bandung' if is_bandung else ''}.
{'Sertakeun rujukan waktu-waktu tangtu di Bandung anu kedah dihindari upami relevan (contona jam sibuk 06:00-09:00 sareng 17:00-20:00).' if is_bandung else ''}
Tips kedah relevan sareng tingkat polusi anu ditampilkeun."""
        }

        task = task_prompts.get(language, task_prompts["id"])
        return f"{data_info}\n\n{task}"

    def _parse_response(self, content: str, language: str) -> Dict[str, Any]:
        try:
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            data = json.loads(content)

            data.setdefault("title", self._get_default_title(language))
            data.setdefault("explanation", "")
            data.setdefault("tips", [])
            data.setdefault("health_impact", "")
            data.setdefault("prevention", "")

            if isinstance(data.get("tips"), list):
                # Normalize tips structure for frontend compatibility
                normalized_tips = []
                for tip in data["tips"]:
                    if not isinstance(tip, dict):
                        # If tip is a string, convert to dict
                        if isinstance(tip, str):
                            normalized_tips.append({
                                "title": "Tips",
                                "description": "Rekomendasi kesehatan" if language == "id" else "Health recommendations",
                                "items": [tip],
                                "category": "Kesehatan" if language == "id" else "Health",
                                "priority": "medium"
                            })
                        continue
                    
                    # Normalize tip structure for frontend compatibility
                    # Frontend expects: title, description, items (array)
                    tip_text = tip.get("tip", tip.get("description", ""))
                    tip_items = tip.get("items", [])
                    
                    # If items is empty but tip text exists, use tip text as single item
                    if not tip_items and tip_text:
                        tip_items = [tip_text]
                    
                    # If still no items, create default
                    if not tip_items:
                        default_text = "Lindungi kesehatan Anda" if language == "id" else "Protect your health"
                        tip_items = [default_text]
                    
                    # Build normalized tip
                    normalized_tip = {
                        "title": tip.get("title") or tip.get("category") or ("Kesehatan" if language == "id" else "Health"),
                        "description": tip.get("description") or tip.get("explanation") or tip_text or "",
                        "items": tip_items,
                        "category": tip.get("category", ""),
                        "priority": tip.get("priority", "medium"),
                    }
                    
                    # Ensure required fields are not empty
                    if not normalized_tip["title"]:
                        normalized_tip["title"] = "Kesehatan" if language == "id" else "Health"
                    if not normalized_tip["description"]:
                        normalized_tip["description"] = "Rekomendasi kesehatan" if language == "id" else "Health recommendations"
                    if not normalized_tip["items"] or len(normalized_tip["items"]) == 0:
                        normalized_tip["items"] = ["Lindungi kesehatan Anda"] if language == "id" else ["Protect your health"]
                    
                    normalized_tips.append(normalized_tip)
                
                data["tips"] = normalized_tips
                
                # If tips array is empty after normalization, use fallback
                if not data["tips"]:
                    return self._get_fallback_tips(None, None, None, language)

            return data
        except json.JSONDecodeError:
            return self._get_fallback_tips(None, None, None, language)

    def _get_default_title(self, language: str) -> str:
        titles = {
            "id": "Tips Kesehatan & Pencegahan",
            "en": "Health & Prevention Tips",
            "su": "Tips Kaséhatan & Pencegahan"
        }
        return titles.get(language, titles["id"])

    def _get_fallback_tips(
        self,
        pm25: Optional[float],
        pm10: Optional[float],
        risk_level: Optional[str],
        language: str
    ) -> Dict[str, Any]:
        """Get fallback tips if LLM error"""
        if language == "id":
            if risk_level == "high":
                tips = [
                    {
                        "title": "Kesehatan",
                        "description": "Lindungi diri dari polusi udara tinggi",
                        "items": [
                            "Gunakan masker N95 saat berada di luar ruangan",
                            "Hindari aktivitas fisik berat di luar ruangan",
                            "Tutup jendela dan gunakan air purifier di dalam ruangan",
                            "Minum air putih lebih banyak untuk membantu detoksifikasi"
                        ],
                        "category": "Kesehatan",
                        "priority": "high"
                    },
                    {
                        "title": "Aktivitas",
                        "description": "Batasi aktivitas di luar ruangan",
                        "items": [
                            "Hindari olahraga di luar ruangan",
                            "Tunda aktivitas non-urgent hingga kualitas udara membaik"
                        ],
                        "category": "Aktivitas",
                        "priority": "high"
                    }
                ]
                health_impact = "Paparan polusi udara tinggi dapat menyebabkan iritasi mata, batuk, sesak napas, memperburuk kondisi pernapasan seperti asma, dan meningkatkan risiko penyakit jantung."
                prevention = "Hindari aktivitas di luar ruangan saat polusi tinggi, gunakan masker N95, pastikan sirkulasi udara di dalam ruangan baik dengan air purifier, dan konsultasi dokter jika mengalami gejala pernapasan."
            elif risk_level == "moderate":
                tips = [
                    {
                        "title": "Kesehatan",
                        "description": "Perlindungan untuk kualitas udara sedang",
                        "items": [
                            "Gunakan masker saat berada di luar ruangan untuk waktu lama",
                            "Batasi aktivitas fisik di luar ruangan, terutama untuk kelompok sensitif",
                            "Pastikan ventilasi ruangan baik"
                        ],
                        "category": "Kesehatan",
                        "priority": "medium"
                    }
                ]
                health_impact = "Paparan polusi udara sedang dapat menyebabkan iritasi ringan pada mata dan saluran pernapasan, terutama pada kelompok sensitif seperti anak-anak, lansia, dan penderita asma."
                prevention = "Kelompok sensitif perlu berhati-hati. Gunakan masker saat beraktivitas di luar, batasi waktu di luar ruangan, dan pastikan ventilasi dalam ruangan baik."
            else:  # low
                tips = [
                    {
                        "title": "Kesehatan",
                        "description": "Kualitas udara baik",
                        "items": [
                            "Tetap jaga kesehatan dengan pola hidup sehat",
                            "Aman untuk melakukan aktivitas di luar ruangan"
                        ],
                        "category": "Kesehatan",
                        "priority": "low"
                    }
                ]
                health_impact = "Kualitas udara baik, risiko kesehatan minimal."
                prevention = "Pertahankan kualitas udara dengan mengurangi penggunaan kendaraan pribadi dan menjaga lingkungan tetap bersih."

            return {
                "title": "Tips Kesehatan & Pencegahan",
                "explanation": (
                    "PM2.5 adalah partikel halus di udara yang dapat masuk ke "
                    "paru-paru dan menyebabkan masalah kesehatan. "
                    f"{'Kondisi saat ini menunjukkan tingkat polusi yang ' + ('tinggi' if risk_level == 'high' else 'sedang' if risk_level == 'moderate' else 'rendah') + '.' if risk_level else 'Kondisi saat ini perlu dipantau.'}"
                ),
                "tips": tips,
                "health_impact": health_impact,
                "prevention": prevention
            }
        elif language == "en":
            if risk_level == "high":
                tips = [
                    {
                        "title": "Health",
                        "description": "Protect yourself from high air pollution",
                        "items": [
                            "Use N95 mask when outdoors",
                            "Avoid heavy physical activity outdoors",
                            "Close windows and use air purifier indoors",
                            "Drink more water to help detoxification"
                        ],
                        "category": "Health",
                        "priority": "high"
                    },
                    {
                        "title": "Activity",
                        "description": "Limit outdoor activities",
                        "items": [
                            "Avoid outdoor exercise",
                            "Postpone non-urgent activities until air quality improves"
                        ],
                        "category": "Activity",
                        "priority": "high"
                    }
                ]
                health_impact = "High air pollution exposure can cause eye irritation, cough, shortness of breath, worsen respiratory conditions like asthma, and increase heart disease risk."
                prevention = "Avoid outdoor activities when pollution is high, use N95 masks, ensure good indoor air circulation with air purifiers, and consult a doctor if experiencing respiratory symptoms."
            elif risk_level == "moderate":
                tips = [
                    {
                        "title": "Health",
                        "description": "Protection for moderate air quality",
                        "items": [
                            "Use mask when outdoors for extended periods",
                            "Limit outdoor physical activity, especially for sensitive groups"
                        ],
                        "category": "Health",
                        "priority": "medium"
                    }
                ]
                health_impact = "Moderate air pollution exposure can cause mild irritation to eyes and respiratory tract, especially in sensitive groups like children, elderly, and asthma patients."
                prevention = "Sensitive groups should be cautious. Use masks when outdoors, limit outdoor time, and ensure good indoor ventilation."
            else:
                tips = [
                    {
                        "title": "Health",
                        "description": "Air quality is good",
                        "items": [
                            "Maintain health with healthy lifestyle",
                            "Safe for outdoor activities"
                        ],
                        "category": "Health",
                        "priority": "low"
                    }
                ]
                health_impact = "Air quality is good, minimal health risk."
                prevention = "Maintain air quality by reducing private vehicle use and keeping the environment clean."

            return {
                "title": "Health & Prevention Tips",
                "explanation": (
                    "PM2.5 are fine particles in the air that can enter the "
                    "lungs and cause health problems. "
                    f"{'Current conditions show ' + ('high' if risk_level == 'high' else 'moderate' if risk_level == 'moderate' else 'low') + ' pollution levels.' if risk_level else 'Current conditions need monitoring.'}"
                ),
                "tips": tips,
                "health_impact": health_impact,
                "prevention": prevention
            }
        else:  # su
            if risk_level == "high":
                tips = [
                    {
                        "title": "Kaséhatan",
                        "description": "Lindungi diri tina polusi udara luhur",
                        "items": [
                            "Gunakeun masker N95 nalika di luar ruangan",
                            "Hindari aktivitas fisik beurat di luar ruangan",
                            "Tutup jandela sareng gunakeun air purifier di jero ruangan"
                        ],
                        "category": "Kaséhatan",
                        "priority": "high"
                    }
                ]
            elif risk_level == "moderate":
                tips = [
                    {
                        "title": "Kaséhatan",
                        "description": "Perlindungan pikeun kualitas udara sedeng",
                        "items": [
                            "Gunakeun masker nalika di luar ruangan",
                            "Watesan aktivitas fisik di luar ruangan"
                        ],
                        "category": "Kaséhatan",
                        "priority": "medium"
                    }
                ]
            else:
                tips = [
                    {
                        "title": "Kaséhatan",
                        "description": "Kualitas udara saé",
                        "items": [
                            "Tetep jaga kaséhatan kalayan pola hirup séhat",
                            "Aman pikeun aktivitas di luar ruangan"
                        ],
                        "category": "Kaséhatan",
                        "priority": "low"
                    }
                ]
            
            return {
                "title": "Tips Kaséhatan & Pencegahan",
                "explanation": "PM2.5 nyaéta partikel halus di udara anu tiasa asup kana paru-paru sareng nyababkeun masalah kaséhatan. Beuki luhur nilaina, beuki bahaya pikeun kaséhatan.",
                "tips": tips,
                "health_impact": "Paparan polusi udara tiasa nyababkeun iritasi panon, batuk, sesak napas, sareng ngorakeun kaayaan pernapasan.",
                "prevention": "Hindari aktivitas di luar ruangan nalika polusi luhur, gunakeun masker, sareng pastikeun sirkulasi udara di jero ruangan saé."
            }


