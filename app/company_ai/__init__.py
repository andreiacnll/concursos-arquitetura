"""CNLL Company Intelligence.

Base backend para perfis empresariais e memoria AI.
"""

from .models import (
    Company,
    CompanyMember,
    CompanyIdentity,
    CompanyMemory,
    CompanyPreferences,
    CompanyProfile,
    MemberCompetences,
    MemberExperience,
    MemberGoals,
    MemberIdentity,
    MemberPreferences,
    MemberProfile,
    MemberVisibility,
)
from .answer_interpreter import InterpretedAnswer, interpret_answer
from .company_context import CompanyContext, build_company_context
from .competition_context import (
    CompetitionContext,
    build_competition_context,
)
from .compatibility_analysis import (
    CompatibilityResult,
    analyze_compatibility,
)
from .recommendation_engine import (
    CompanyRecommendation,
    generate_recommendation,
)
from .recommendation_presenter import (
    RecommendationCardData,
    build_recommendation_card,
)
from .router import router

__all__ = [
    "Company",
    "CompanyMember",
    "CompanyIdentity",
    "CompanyMemory",
    "CompanyPreferences",
    "CompanyProfile",
    "CompanyContext",
    "CompetitionContext",
    "CompatibilityResult",
    "CompanyRecommendation",
    "RecommendationCardData",
    "MemberCompetences",
    "MemberExperience",
    "MemberGoals",
    "MemberIdentity",
    "MemberPreferences",
    "MemberProfile",
    "MemberVisibility",
    "InterpretedAnswer",
    "interpret_answer",
    "build_company_context",
    "build_competition_context",
    "analyze_compatibility",
    "generate_recommendation",
    "build_recommendation_card",
    "router",
]
