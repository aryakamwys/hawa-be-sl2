"""
Weather API Endpoints
Endpoints for weather recommendations and knowledge management
"""
import os
import tempfile
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.exceptions import handle_google_sheets_error
from app.db.postgres import get_db
from app.services.notification.whatsapp_service import WhatsAppService
from app.services.weather.groq_heatmap_tips_service import GroqHeatmapTipsService
from app.services.weather.heatmap_processor import HeatmapProcessor
from app.services.weather.recommendation_service import WeatherRecommendationService
from app.services.weather.sheets_cache_service import (
    get_cached_sheets_data,
    get_realtime_sheets_data
)
from app.services.weather.spreadsheet_service import SpreadsheetService
from app.services.weather.openmeteo_service import OpenMeteoService

if TYPE_CHECKING:
    from app.db.models.user import User

router = APIRouter(prefix="/weather", tags=["weather"])


class WeatherDataRequest(BaseModel):
    """Request for direct weather data"""
    pm25: float | None = None
    pm10: float | None = None
    o3: float | None = None
    no2: float | None = None
    so2: float | None = None
    co: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    location: str = "Bandung"
    timestamp: str | None = None


class GoogleSheetsRequest(BaseModel):
    """Request to fetch from Google Sheets"""
    spreadsheet_id: str
    worksheet_name: str = "Sheet1"


class SendNotificationRequest(BaseModel):
    """Request to send WhatsApp notification"""
    send_whatsapp: bool = False
    phone_number: str | None = None  # Optional, will use from user profile if not provided


class GoogleSheetsRequestWithNotification(BaseModel):
    """Request wrapper for Google Sheets with optional notification"""
    spreadsheet_id: str
    worksheet_name: str = "Sheet1"
    notification: Optional[SendNotificationRequest] = None

    class Config:
        # Allow extra fields for backward compatibility
        extra = "ignore"


@router.post("/recommendation", status_code=status.HTTP_200_OK)
def get_recommendation(
    weather_data: Optional[WeatherDataRequest] = None,
    notification: Optional[SendNotificationRequest] = None,
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized weather recommendation

    Can use direct weather_data or upload spreadsheet
    Optional: Send notification to WhatsApp
    """
    service = WeatherRecommendationService(db)

    try:
        weather_dict = weather_data.dict() if weather_data else None
        recommendation = service.get_personalized_recommendation(
            user=current_user,
            weather_data=weather_dict
        )

        # Send WhatsApp notification if requested
        if notification and notification.send_whatsapp:
            whatsapp_service = WhatsAppService()
            phone_number = notification.phone_number or current_user.phone_e164

            if phone_number:
                # Only send if risk level is medium or higher
                risk_level = recommendation.get("risk_level", "").lower()
                if risk_level in ["medium", "high", "critical"]:
                    success = whatsapp_service.send_weather_warning_instant(
                        phone_number=phone_number,
                        recommendation=recommendation,
                        language=current_user.language.value if current_user.language else "id"
                    )
                    recommendation["notification_sent"] = success
                else:
                    recommendation["notification_sent"] = False
                    recommendation["notification_skipped"] = "Risk level too low"
            else:
                recommendation["notification_sent"] = False
                recommendation["notification_error"] = "Phone number not provided"

        return recommendation
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except (KeyError, AttributeError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing recommendation data: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating recommendation: {str(e)}"
        ) from e


@router.post("/recommendation/from-google-sheets", status_code=status.HTTP_200_OK)
def get_recommendation_from_google_sheets(
    request: GoogleSheetsRequestWithNotification,
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recommendation from Google Sheets

    Args:
        request: GoogleSheetsRequestWithNotification with spreadsheet_id, worksheet_name, and optional notification

    Request Body Format:
    {
        "spreadsheet_id": "1Cv0PPUtZjIFlVSprD-FfvQDkUV4thy5qsH4IOMl3cyA",
        "worksheet_name": "Sheet1",
        "notification": null  // optional
    }

    Returns:
        Personalized recommendation
    """
    service = WeatherRecommendationService(db)

    try:
        recommendation = service.get_personalized_recommendation(
            user=current_user,
            google_sheets_id=request.spreadsheet_id,
            google_sheets_worksheet=request.worksheet_name
        )

        # Send WhatsApp notification if requested
        notification = request.notification
        if notification and notification.send_whatsapp:
            whatsapp_service = WhatsAppService()
            phone_number = notification.phone_number or current_user.phone_e164

            if phone_number:
                risk_level = recommendation.get("risk_level", "").lower()
                if risk_level in ["medium", "high", "critical"]:
                    success = whatsapp_service.send_weather_warning_instant(
                        phone_number=phone_number,
                        recommendation=recommendation,
                        language=current_user.language.value if current_user.language else "id"
                    )
                    recommendation["notification_sent"] = success
                else:
                    recommendation["notification_sent"] = False
                    recommendation["notification_skipped"] = "Risk level too low"
            else:
                recommendation["notification_sent"] = False
                recommendation["notification_error"] = "Phone number not provided"

        return recommendation
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise handle_google_sheets_error(e)


@router.post("/recommendation/from-spreadsheet", status_code=status.HTTP_200_OK)
def get_recommendation_from_spreadsheet(
    file: UploadFile = File(...),
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recommendation from spreadsheet upload

    Supported formats: .xlsx, .xls, .csv
    """

    # Validate file type
    allowed_extensions = ['.xlsx', '.xls', '.csv']
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        content = file.file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        service = WeatherRecommendationService(db)
        recommendation = service.get_personalized_recommendation(
            user=current_user,
            spreadsheet_path=tmp_path
        )
        return recommendation
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File error: {str(e)}"
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except (OSError, IOError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File system error: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing spreadsheet: {str(e)}"
        ) from e
    finally:
        # Cleanup
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/heatmap", status_code=status.HTTP_200_OK)
def get_heatmap_data(
    current_user: "User" = Depends(get_current_user),
    worksheet_name: str = Query(default="Sheet1", description="Worksheet name"),
    force_refresh: bool = Query(
        default=False,
        description="Force refresh from Google Sheets (bypass cache)"
    )
):
    """
    Get heatmap data from Google Sheets for map visualization.
    This endpoint can be accessed by all logged-in users.

    Data is taken from heatmap spreadsheet with format:
    - Location, Latitude, Longitude, PM2.5, PM10, Air Quality, Risk Score, Color, Device ID

    Returns:
        Array of heatmap points with format ready for frontend map visualization
    """
    heatmap_spreadsheet_id = "1p69Ae67JGlScrMlSDnebuZMghXYMY7IykiT1gQwello"

    try:
        # Use realtime cache (1 second) for heatmap data
        raw_data = get_realtime_sheets_data(
            spreadsheet_id=heatmap_spreadsheet_id,
            worksheet_name=worksheet_name,
            force_refresh=force_refresh
        )

        return HeatmapProcessor.process_heatmap_points(
            raw_data=raw_data,
            spreadsheet_id=heatmap_spreadsheet_id,
            worksheet_name=worksheet_name
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise handle_google_sheets_error(e)


@router.get("/heatmap/info", status_code=status.HTTP_200_OK)
def get_heatmap_info(
    current_user: "User" = Depends(get_current_user),
    language: Optional[str] = Query(
        default=None,
        description="Language (id, en, su). Optional, default from user profile"
    )
):
    """
    Get information/legend for heatmap.
    Explains the meaning of colors and categories on the map.

    Language will automatically match user profile (current_user.language).
    Query parameter language is only used as override if needed.

    Returns:
        Information about risk level categories and color meanings in heatmap
        in language matching user profile
    """
    user_lang = current_user.language.value if current_user.language else "id"

    if language:
        user_lang = language

    info_data = {
        "id": {
            "title": "Informasi Peta Sebaran",
            "description": "Peta ini menampilkan sebaran kualitas udara di berbagai lokasi. Setiap warna menunjukkan tingkat risiko polusi udara.",
            "categories": [
                {
                    "color": "red",
                    "label": "Tinggi",
                    "description": "PM2.5 > 75 μg/m³",
                    "risk_level": "high",
                    "meaning": "Kualitas udara tidak sehat. Hindari aktivitas di luar ruangan."
                },
                {
                    "color": "orange",
                    "label": "Sedang",
                    "description": "PM2.5 35-75 μg/m³",
                    "risk_level": "moderate",
                    "meaning": "Kualitas udara sedang. Kelompok sensitif perlu berhati-hati."
                },
                {
                    "color": "green",
                    "label": "Rendah",
                    "description": "PM2.5 < 35 μg/m³",
                    "risk_level": "low",
                    "meaning": "Kualitas udara baik. Aman untuk aktivitas di luar ruangan."
                }
            ],
            "pm25_explanation": "PM2.5: Partikel halus di udara yang dapat masuk ke paru-paru dan menyebabkan masalah kesehatan.",
            "pm10_explanation": "PM10: Partikel debu yang lebih besar yang dapat mengiritasi saluran pernapasan."
        },
        "en": {
            "title": "Distribution Map Information",
            "description": "This map shows the distribution of air quality at various locations. Each color indicates the level of air pollution risk.",
            "categories": [
                {
                    "color": "red",
                    "label": "High",
                    "description": "PM2.5 > 75 μg/m³",
                    "risk_level": "high",
                    "meaning": "Unhealthy air quality. Avoid outdoor activities."
                },
                {
                    "color": "orange",
                    "label": "Moderate",
                    "description": "PM2.5 35-75 μg/m³",
                    "risk_level": "moderate",
                    "meaning": "Moderate air quality. Sensitive groups should be cautious."
                },
                {
                    "color": "green",
                    "label": "Low",
                    "description": "PM2.5 < 35 μg/m³",
                    "risk_level": "low",
                    "meaning": "Good air quality. Safe for outdoor activities."
                }
            ],
            "pm25_explanation": "PM2.5: Fine particles in the air that can enter the lungs and cause health problems.",
            "pm10_explanation": "PM10: Larger dust particles that can irritate the respiratory tract."
        },
        "su": {
            "title": "Informasi Peta Sebaran",
            "description": "Peta ieu nampilkeun sebaran kualitas udara di sababaraha lokasi. Unggal warna nunjukkeun tingkat risiko polusi udara.",
            "categories": [
                {
                    "color": "red",
                    "label": "Tinggi",
                    "description": "PM2.5 > 75 μg/m³",
                    "risk_level": "high",
                    "meaning": "Kualitas udara henteu séhat. Hindari aktivitas di luar ruangan."
                },
                {
                    "color": "orange",
                    "label": "Sedang",
                    "description": "PM2.5 35-75 μg/m³",
                    "risk_level": "moderate",
                    "meaning": "Kualitas udara sedeng. Kelompok sensitif kedah ati-ati."
                },
                {
                    "color": "green",
                    "label": "Rendah",
                    "description": "PM2.5 < 35 μg/m³",
                    "risk_level": "low",
                    "meaning": "Kualitas udara saé. Aman pikeun aktivitas di luar ruangan."
                }
            ],
            "pm25_explanation": "PM2.5: Partikel halus di udara anu tiasa asup kana paru-paru sareng nyababkeun masalah kaséhatan.",
            "pm10_explanation": "PM10: Partikel debu anu langkung ageung anu tiasa ngairitasi saluran pernapasan."
        }
    }

    return info_data.get(user_lang, info_data["id"])


@router.get("/heatmap/tips", status_code=status.HTTP_200_OK)
def get_heatmap_tips(
    current_user: "User" = Depends(get_current_user),
    pm25: Optional[float] = Query(
        default=None,
        description="PM2.5 value to generate tips"
    ),
    pm10: Optional[float] = Query(
        default=None,
        description="PM10 value to generate tips"
    ),
    air_quality: Optional[str] = Query(
        default=None,
        description="Air quality status"
    ),
    risk_level: Optional[str] = Query(
        default=None,
        description="Risk level (high, moderate, low)"
    ),
    location: Optional[str] = Query(
        default=None,
        description="Location name"
    ),
    language: Optional[str] = Query(
        default=None,
        description="Language (id, en, su). Optional override, default automatically from user profile"
    )
):
    """
    Get AI-generated tips and recommendations based on pollution level.
    Uses Groq LLM to generate explainable AI tips.

    Query Parameters:
        - pm25, pm10: Pollution values (optional, can be from heatmap point)
        - air_quality: Air quality status (optional)
        - risk_level: Risk level (optional)
        - location: Location name (optional)
        - language: Language (optional, default from user profile)

    Returns:
        AI-generated tips and explanations based on pollution data
        Language matches user's language preference (id, en, or su)
    """
    user_lang = current_user.language.value if current_user.language else "id"
    if language:
        user_lang = language

    tips_service = GroqHeatmapTipsService()

    try:
        tips = tips_service.generate_tips(
            pm25=pm25,
            pm10=pm10,
            air_quality=air_quality,
            risk_level=risk_level,
            location=location,
            language=user_lang
        )

        # Ensure tips array exists and is not empty
        if not tips or not isinstance(tips, dict):
            raise ValueError("Invalid tips response from service")
        
        tips_array = tips.get("tips", [])
        if not tips_array or not isinstance(tips_array, list):
            # If tips array is missing or empty, use fallback
            tips = tips_service._get_fallback_tips(pm25, pm10, risk_level, user_lang)

        return {
            "success": True,
            "language": user_lang,
            "data": tips,
            "source": "groq_llm"
        }

    except (ValueError, KeyError, AttributeError) as e:
        error_msg = str(e)
        try:
            fallback_tips = tips_service._get_fallback_tips(
                pm25, pm10, risk_level, user_lang
            )

            return {
                "success": True,
                "language": user_lang,
                "data": fallback_tips,
                "source": "fallback",
                "error": error_msg
            }
        except Exception:
            return {
                "success": False,
                "language": user_lang,
                "data": {
                    "title": "Tips Kesehatan & Pencegahan",
                    "explanation": "Tidak dapat memuat tips saat ini. Silakan coba lagi nanti.",
                    "tips": [],
                    "health_impact": "",
                    "prevention": ""
                },
                "source": "error",
                "error": error_msg
            }
    except Exception as e:
        error_msg = str(e)
        try:
            fallback_tips = tips_service._get_fallback_tips(
                pm25, pm10, risk_level, user_lang
            )

            return {
                "success": True,
                "language": user_lang,
                "data": fallback_tips,
                "source": "fallback",
                "error": error_msg
            }
        except Exception:
            return {
                "success": False,
                "language": user_lang,
                "data": {
                    "title": "Tips Kesehatan & Pencegahan",
                    "explanation": "Tidak dapat memuat tips saat ini. Silakan coba lagi nanti.",
                    "tips": [],
                    "health_impact": "",
                    "prevention": ""
                },
                "source": "error",
                "error": error_msg
            }


@router.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    """Health check endpoint for weather service"""
    return {
        "status": "healthy",
        "service": "weather-recommendation"
    }


@router.get("/analytics/current", status_code=status.HTTP_200_OK)
def get_current_weather_analytics(
    current_user: "User" = Depends(get_current_user),
    city: str = Query(default="Bandung", description="City name"),
    country_code: str = Query(default="ID", description="Country code")
):
    """
    Get current weather analytics from Open-Meteo API (free, no API key required)
    
    Returns current weather data including temperature, humidity, pressure, wind, etc.
    """
    try:
        weather_service = OpenMeteoService()
        result = weather_service.get_current_weather(city=city, country_code=country_code)
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to fetch weather data")
            )
        
        return {
            "success": True,
            "data": result.get("data"),
            "source": "open-meteo"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching weather analytics: {str(e)}"
        )


@router.get("/analytics/forecast", status_code=status.HTTP_200_OK)
def get_weather_forecast_analytics(
    current_user: "User" = Depends(get_current_user),
    city: str = Query(default="Bandung", description="City name"),
    country_code: str = Query(default="ID", description="Country code"),
    days: int = Query(default=5, ge=1, le=16, description="Number of forecast days (max 16)")
):
    """
    Get weather forecast analytics from Open-Meteo API (free, no API key required)
    
    Returns weather forecast with daily data points.
    """
    try:
        weather_service = OpenMeteoService()
        result = weather_service.get_forecast(city=city, country_code=country_code, days=days)
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to fetch forecast data")
            )
        
        return {
            "success": True,
            "data": result.get("data"),
            "source": "open-meteo"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching forecast analytics: {str(e)}"
        )


@router.get("/analytics/hourly", status_code=status.HTTP_200_OK)
def get_hourly_weather_forecast(
    current_user: "User" = Depends(get_current_user),
    city: str = Query(default="Bandung", description="City name"),
    country_code: str = Query(default="ID", description="Country code"),
    hours: int = Query(default=24, ge=1, le=240, description="Number of hours to forecast (max 240)")
):
    """
    Get hourly weather forecast from Open-Meteo API (free, no API key required)
    
    Returns hourly weather forecast data.
    """
    try:
        weather_service = OpenMeteoService()
        result = weather_service.get_hourly_forecast(city=city, country_code=country_code, hours=hours)
        
        if result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to fetch hourly forecast data")
            )
        
        return {
            "success": True,
            "data": result.get("data"),
            "source": "open-meteo"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching hourly forecast: {str(e)}"
        )


@router.get("/analytics/summary", status_code=status.HTTP_200_OK)
def get_weather_analytics_summary(
    current_user: "User" = Depends(get_current_user),
    city: str = Query(default="Bandung", description="City name"),
    country_code: str = Query(default="ID", description="Country code")
):
    """
    Get comprehensive weather analytics summary
    
    Combines current weather, forecast, and air quality recommendations.
    """
    try:
        weather_service = OpenMeteoService()
        
        # Get current weather
        current_result = weather_service.get_current_weather(city=city, country_code=country_code)
        forecast_result = weather_service.get_forecast(city=city, country_code=country_code, days=5)
        
        # Get air quality recommendation if available
        db = next(get_db())
        recommendation_service = WeatherRecommendationService(db)
        
        # Build weather data for recommendation
        current_data = current_result.get("data", {}).get("current", {}) if current_result.get("data") else {}
        weather_data = {
            "temperature": current_data.get("temperature"),
            "humidity": current_data.get("humidity"),
            "pressure": current_data.get("pressure"),
            "wind_speed": current_data.get("wind_speed"),
            "location": city
        }
        
        try:
            recommendation = recommendation_service.get_personalized_recommendation(
                user=current_user,
                weather_data=weather_data
            )
        except Exception:
            recommendation = None
        
        summary = {
            "current": current_result.get("data") if not current_result.get("error") else None,
            "forecast": forecast_result.get("data") if not forecast_result.get("error") else None,
            "recommendation": recommendation,
            "errors": {
                "current": current_result.get("error"),
                "forecast": forecast_result.get("error")
            }
        }
        
        return {
            "success": True,
            "data": summary,
            "source": "open-meteo"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Service configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating analytics summary: {str(e)}"
        )


@router.get("/analytics/compare", status_code=status.HTTP_200_OK)
def compare_air_quality_trends(
    current_user: "User" = Depends(get_current_user),
    primary_city: str = Query(default="Bandung", description="Primary city to analyze"),
    secondary_city: str | None = Query(default=None, description="Optional comparison city"),
    hours: int = Query(default=72, ge=12, le=168, description="Hours of history to load (max 7 days)")
):
    """
    Compare historical air quality (PM2.5 & PM10) between cities.

    Uses Open-Meteo Air Quality API (no API key required).
    """
    weather_service = OpenMeteoService()

    try:
        primary = weather_service.get_air_quality_history(city=primary_city, hours=hours)
        if primary.get("error"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=primary.get("error", "Failed to fetch primary city data")
            )

        secondary_data = None
        if secondary_city:
            secondary = weather_service.get_air_quality_history(city=secondary_city, hours=hours)
            if secondary.get("error"):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=secondary.get("error", "Failed to fetch secondary city data")
                )
            secondary_data = secondary.get("data")

        return {
            "success": True,
            "data": {
                "primary": primary.get("data"),
                "secondary": secondary_data
            },
            "source": "open-meteo"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error comparing air quality trends: {str(e)}"
        )

