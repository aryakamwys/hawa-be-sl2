#!/usr/bin/env python3
"""
Script untuk populate weather_knowledge table dengan initial data
Jalankan: python scripts/populate_weather_knowledge.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.db.postgres import get_db
from app.services.weather.vector_service import VectorService

# Knowledge base data (Bahasa Indonesia)
KNOWLEDGE_DATA_ID = [
    {
        "content": "PM2.5 tinggi (AQI > 150) dapat menyebabkan gangguan pernapasan, terutama pada anak-anak dan lansia. Gunakan masker N95 saat keluar rumah.",
        "metadata": {"source": "WHO", "category": "health", "severity": "high"},
        "language": "id"
    },
    {
        "content": "Hindari olahraga outdoor saat PM2.5 > 150 atau PM10 > 200. Olahraga indoor lebih aman untuk kesehatan.",
        "metadata": {"source": "EPA", "category": "activity", "severity": "medium"},
        "language": "id"
    },
    {
        "content": "Tutup jendela dan gunakan air purifier saat polusi tinggi. PM2.5 dapat masuk ke dalam rumah melalui ventilasi.",
        "metadata": {"source": "Health Guide", "category": "indoor", "severity": "medium"},
        "language": "id"
    },
    {
        "content": "Masker N95 lebih efektif daripada masker biasa untuk melindungi dari PM2.5. Pastikan masker pas di wajah tanpa celah.",
        "metadata": {"source": "CDC", "category": "protection", "severity": "high"},
        "language": "id"
    },
    {
        "content": "Paparan PM2.5 jangka panjang dapat meningkatkan risiko penyakit jantung, stroke, dan kanker paru-paru. Batasi waktu di luar ruangan saat polusi tinggi.",
        "metadata": {"source": "WHO", "category": "health", "severity": "critical"},
        "language": "id"
    },
    {
        "content": "Saat AQI > 100, kurangi aktivitas outdoor. Jika AQI > 150, hindari semua aktivitas outdoor yang berat.",
        "metadata": {"source": "EPA", "category": "activity", "severity": "medium"},
        "language": "id"
    },
    {
        "content": "Gunakan air purifier dengan HEPA filter untuk mengurangi PM2.5 di dalam ruangan. Ganti filter secara berkala.",
        "metadata": {"source": "Health Guide", "category": "indoor", "severity": "low"},
        "language": "id"
    },
    {
        "content": "Anak-anak dan lansia lebih rentan terhadap efek polusi udara. Berikan perhatian ekstra saat AQI tinggi.",
        "metadata": {"source": "WHO", "category": "health", "severity": "high"},
        "language": "id"
    },
    {
        "content": "PM10 dapat menyebabkan iritasi mata, hidung, dan tenggorokan. Gunakan kacamata dan masker saat polusi tinggi.",
        "metadata": {"source": "Health Guide", "category": "health", "severity": "medium"},
        "language": "id"
    },
    {
        "content": "Cek kualitas udara sebelum beraktivitas outdoor. Gunakan aplikasi atau website AQI untuk monitoring real-time.",
        "metadata": {"source": "EPA", "category": "monitoring", "severity": "low"},
        "language": "id"
    },
]

# English knowledge
KNOWLEDGE_DATA_EN = [
    {
        "content": "High PM2.5 levels (AQI > 150) can cause respiratory problems, especially in children and elderly. Use N95 masks when going outside.",
        "metadata": {"source": "WHO", "category": "health", "severity": "high"},
        "language": "en"
    },
    {
        "content": "Avoid outdoor exercise when PM2.5 > 150 or PM10 > 200. Indoor exercise is safer for health.",
        "metadata": {"source": "EPA", "category": "activity", "severity": "medium"},
        "language": "en"
    },
    {
        "content": "Close windows and use air purifier when pollution is high. PM2.5 can enter homes through ventilation.",
        "metadata": {"source": "Health Guide", "category": "indoor", "severity": "medium"},
        "language": "en"
    },
    {
        "content": "N95 masks are more effective than regular masks for protection against PM2.5. Ensure the mask fits snugly without gaps.",
        "metadata": {"source": "CDC", "category": "protection", "severity": "high"},
        "language": "en"
    },
    {
        "content": "Long-term exposure to PM2.5 can increase risk of heart disease, stroke, and lung cancer. Limit time outdoors when pollution is high.",
        "metadata": {"source": "WHO", "category": "health", "severity": "critical"},
        "language": "en"
    },
]


def populate_knowledge():
    """Populate weather_knowledge table with initial data"""
    db = next(get_db())
    vector_service = VectorService()
    
    try:
        print("Populating weather_knowledge table...")
        print(f"Vector service available: {vector_service.use_pgvector}")
        print(f"Embedding model available: {vector_service.embedding_model is not None}\n")
        
        # Add Indonesian knowledge
        print("Adding Indonesian knowledge...")
        for idx, data in enumerate(KNOWLEDGE_DATA_ID, 1):
            try:
                knowledge = vector_service.add_knowledge(
                    db=db,
                    content=data["content"],
                    metadata=data["metadata"],
                    language=data["language"]
                )
                print(f"  [{idx}/{len(KNOWLEDGE_DATA_ID)}] ✓ Added: {data['content'][:50]}...")
            except Exception as e:
                print(f"  [{idx}/{len(KNOWLEDGE_DATA_ID)}] ✗ Error: {e}")
        
        # Add English knowledge
        print("\nAdding English knowledge...")
        for idx, data in enumerate(KNOWLEDGE_DATA_EN, 1):
            try:
                knowledge = vector_service.add_knowledge(
                    db=db,
                    content=data["content"],
                    metadata=data["metadata"],
                    language=data["language"]
                )
                print(f"  [{idx}/{len(KNOWLEDGE_DATA_EN)}] ✓ Added: {data['content'][:50]}...")
            except Exception as e:
                print(f"  [{idx}/{len(KNOWLEDGE_DATA_EN)}] ✗ Error: {e}")
        
        print("\n✅ Knowledge base populated successfully!")
        print(f"   Total: {len(KNOWLEDGE_DATA_ID) + len(KNOWLEDGE_DATA_EN)} entries")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate_knowledge()






