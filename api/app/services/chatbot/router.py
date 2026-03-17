"""Intent classification for the chatbot."""
from enum import StrEnum
from typing import Any


class Intent(StrEnum):
    SCORE_QUERY = "score_query"           # e.g. "What is my ★12 clear rate?"
    SONG_RECOMMENDATION = "song_recommendation"  # e.g. "Recommend songs for my level"
    TABLE_INFO = "table_info"             # e.g. "What is the insane difficulty table?"
    GENERAL_BMS = "general_bms"           # General BMS knowledge questions
    CASUAL = "casual"                     # Small talk / casual conversation
    UNKNOWN = "unknown"


INTENT_KEYWORDS: dict[Intent, list[str]] = {
    Intent.SCORE_QUERY: ["클리어", "스코어", "점수", "내 기록", "bp", "콤보"],
    Intent.SONG_RECOMMENDATION: ["추천", "어떤 곡", "연습할", "다음에 할"],
    Intent.TABLE_INFO: ["난이도표", "발광", "통상", "삭제", "보면"],
    Intent.GENERAL_BMS: ["bms", "beatoraja", "lr2", "qwilight", "보면", "채보"],
    Intent.CASUAL: ["안녕", "고마워", "감사", "잘 부탁"],
}


def classify_intent(message: str) -> Intent:
    """
    Simple keyword-based intent classifier.
    In production, replace with an LLM-based classifier.
    """
    message_lower = message.lower()

    for intent, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                return intent

    return Intent.UNKNOWN


def build_system_prompt(intent: Intent, user_context: dict[str, Any] | None = None) -> str:
    """Build a system prompt based on the detected intent."""
    base_prompt = (
        "당신은 OJIK BMS의 AI 어시스턴트입니다. "
        "BMS(Be-Music Source) 리듬게임 플레이어를 돕는 전문 챗봇입니다. "
        "한국어로 답변하세요."
    )

    intent_prompts = {
        Intent.SCORE_QUERY: (
            "\n\n사용자의 플레이 기록과 스코어에 대한 질문입니다. "
            "제공된 사용자 데이터를 바탕으로 정확한 정보를 제공하세요."
        ),
        Intent.SONG_RECOMMENDATION: (
            "\n\n곡 추천 요청입니다. "
            "사용자의 실력 수준을 고려하여 적절한 난이도의 곡을 추천하세요."
        ),
        Intent.TABLE_INFO: (
            "\n\n난이도표 관련 질문입니다. "
            "발광 BMS, 통상 BMS 등 난이도표 정보를 정확하게 설명하세요."
        ),
        Intent.GENERAL_BMS: (
            "\n\nBMS 일반 지식 질문입니다. "
            "BMS 클라이언트, 기능, 설정 등에 대해 도움을 제공하세요."
        ),
    }

    additional = intent_prompts.get(intent, "")
    return base_prompt + additional
