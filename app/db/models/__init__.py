"""Model package initializer to ensure SQLAlchemy mappings are registered."""

# Import all model modules so relationship string lookups (e.g. "ComplianceRecord")
# can be resolved when SQLAlchemy configures mappers.
from app.db.models.user import User  # noqa: F401
from app.db.models.compliance import ComplianceRecord  # noqa: F401
from app.db.models.feedback import CommunityFeedback, FeedbackVote  # noqa: F401
from app.db.models.weather_knowledge import WeatherKnowledge  # noqa: F401






