"""
Main Weather Recommendation Service
Combines all services to generate personalized recommendations
Enhanced with AI caching and improved vector-based personalization
"""
import json
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from app.db.models.user import User
from app.services.weather.groq_service import GroqWeatherService
from app.services.weather.vector_service import VectorService
from app.services.weather.spreadsheet_service import SpreadsheetService
from app.services.weather.ai_cache_service import (
    get_ai_cache_service,
    generate_cache_key
)


class WeatherRecommendationService:
    """Main service to generate personalized weather recommendations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.groq_service = GroqWeatherService()
        self.vector_service = VectorService()
        self.spreadsheet_service = SpreadsheetService()
        self.ai_cache = get_ai_cache_service()
    
    def get_personalized_recommendation(
        self,
        user: User,
        weather_data: Dict[str, Any] | None = None,
        spreadsheet_path: str | None = None,
        google_sheets_id: str | None = None,
        google_sheets_worksheet: str = "Sheet1"
    ) -> Dict[str, Any]:
        """
        Generate personalized recommendation for user
        
        Args:
            user: User object with complete profile
            weather_data: Direct weather data (optional)
            spreadsheet_path: Path to spreadsheet file (optional)
        
        Returns:
            Dictionary with structured recommendations
        """
        # 1. Get atau load weather data
        if weather_data is None:
            if google_sheets_id:
                # Read from Google Sheets
                raw_data = self.spreadsheet_service.read_from_google_sheets(
                    spreadsheet_id=google_sheets_id,
                    worksheet_name=google_sheets_worksheet
                )
                weather_data = self.spreadsheet_service.process_bmkg_data(raw_data)
            elif spreadsheet_path:
                # Read from local file
                raw_data = self.spreadsheet_service.read_weather_data(spreadsheet_path)
                weather_data = self.spreadsheet_service.process_bmkg_data(raw_data)
            else:
                raise ValueError(
                    "Either weather_data, spreadsheet_path, or google_sheets_id must be provided"
                )
        
        # Validate weather data
        if not self.spreadsheet_service.validate_weather_data(weather_data):
            raise ValueError("Invalid weather data: missing required fields")
        
        # Check AI cache first
        cache_key = generate_cache_key(user.id, weather_data)
        cached_recommendation = self.ai_cache.get_cached_recommendation(cache_key)
        if cached_recommendation:
            return cached_recommendation
        
        # 2. Build user profile
        user_profile = self._build_user_profile(user)
        
        # 3. Get relevant context from vector DB (enhanced with more specific query)
        query_context = self._build_query_context(weather_data, user_profile)
        context_knowledge = self.vector_service.search_similar(
            self.db,
            query_context,
            language=user.language.value if user.language else "id",
            limit=5,  # Increased from 3 to 5 for more context
            threshold=0.6  # Lower threshold from 0.7 to 0.6 for more results
        )
        
        # 4. Generate recommendation dengan Groq LLM
        recommendation = self.groq_service.generate_recommendation(
            weather_data=weather_data,
            user_profile=user_profile,
            context_knowledge=context_knowledge,
            language=user.language.value if user.language else "id",
            use_streaming=False
        )
        
        # 5. Add metadata
        recommendation["metadata"] = {
            "user_id": user.id,
            "location": weather_data.get("location", "Unknown"),
            "timestamp": weather_data.get("timestamp"),
            "language": user.language.value if user.language else "id",
            "cached": False
        }
        
        # 6. Cache recommendation
        self.ai_cache.set_cached_recommendation(cache_key, recommendation)
        
        return recommendation
    
    def _build_user_profile(self, user: User) -> Dict[str, Any]:
        """Build user profile dictionary from User model"""
        profile = {
            'age': user.age,
            'occupation': user.occupation,
            'location': user.location,
            'activity_level': user.activity_level,
            'sensitivity_level': user.sensitivity_level or "medium",
            'health_conditions': 'Tidak ada'
        }
        
        # Decrypt health conditions if available
        if user.health_conditions_encrypted:
            try:
                from app.core.security import decrypt_user_health_data
                profile['health_conditions'] = decrypt_user_health_data(
                    user.health_conditions_encrypted
                )
            except Exception:
                profile['health_conditions'] = 'Data tidak tersedia'
        
        return profile
    
    def _build_query_context(
        self,
        weather_data: Dict[str, Any],
        user_profile: Dict[str, Any]
    ) -> str:
        """
        Build query context for vector search with more detail.
        Enhanced personalization based on complete user profile.
        """
        location = weather_data.get('location', 'Bandung')
        occupation = user_profile.get('occupation', '')
        sensitivity = user_profile.get('sensitivity_level', 'medium')
        age = user_profile.get('age')
        activity = user_profile.get('activity_level', 'moderate')
        health = user_profile.get('health_conditions', 'Tidak ada')
        
        # Build more specific query for similarity search
        query_parts = [f"polusi udara {location}"]
        
        # Add occupation context
        if occupation:
            # Categorize occupation for better context
            if any(word in occupation.lower() for word in ['outdoor', 'luar', 'lapangan', 'konstruksi', 'tukang']):
                query_parts.append("pekerja outdoor")
            elif any(word in occupation.lower() for word in ['indoor', 'dalam', 'kantor', 'office']):
                query_parts.append("pekerja indoor")
            else:
                query_parts.append(f"untuk {occupation}")
        
        # Add sensitivity level
        if sensitivity == "high":
            query_parts.append("kelompok sensitif tinggi")
        elif sensitivity == "low":
            query_parts.append("kelompok sensitif rendah")
        else:
            query_parts.append(f"sensitivitas {sensitivity}")
        
        # Add age context
        if age:
            if age < 18:
                query_parts.append("anak-anak remaja")
            elif age > 60:
                query_parts.append("lansia")
            elif age < 30:
                query_parts.append("dewasa muda")
        
        # Add activity level
        if activity == "active":
            query_parts.append("aktivitas fisik tinggi")
        elif activity == "sedentary":
            query_parts.append("aktivitas fisik rendah")
        else:
            query_parts.append(f"aktivitas fisik {activity}")
        
        # Add health conditions context
        health_lower = str(health).lower()
        if "asma" in health_lower or "asthma" in health_lower:
            query_parts.append("penderita asma")
        if "jantung" in health_lower or "heart" in health_lower or "kardiovaskular" in health_lower:
            query_parts.append("penyakit jantung")
        if "paru" in health_lower or "lung" in health_lower or "respirasi" in health_lower:
            query_parts.append("masalah pernapasan")
        if "diabetes" in health_lower:
            query_parts.append("penderita diabetes")
        
        return " ".join(query_parts)

