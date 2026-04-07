"""Claude API를 활용한 SNS 성과 AI 분석"""

import json
import logging

import requests

from config import ANTHROPIC_API_KEY

logger = logging.getLogger("sns_performance")

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-5"


def _call_claude(prompt, max_tokens=1200):
    """Claude API 호출"""
    if not ANTHROPIC_API_KEY:
        return None

    try:
        resp = requests.post(
            API_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["content"][0]["text"]
        else:
            logger.warning(f"Claude API 에러: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Claude API 호출 실패: {e}")
        return None


def generate_daily_insight(channel_summaries, channel_posts, analysis, anomalies):
    """일일 성과 데이터를 분석하여 자연어 인사이트를 생성합니다.

    Returns:
        Dict - {"요약": str, "추천": List[str], "주의": List[str]}
    """
    if not ANTHROPIC_API_KEY:
        return {
            "요약": "AI 인사이트 기능이 설정되지 않았습니다. .env에 ANTHROPIC_API_KEY를 추가하세요.",
            "추천": [],
            "주의": [],
        }

    # 데이터 요약 (토큰 절약)
    summary_text = ""
    for s in channel_summaries:
        ch = s.get("채널", "")
        summary_text += f"- {ch}: 게시물 {s.get('총게시물수', 0)}개, "
        summary_text += f"조회수 {s.get('총조회수', 0):,}, "
        summary_text += f"좋아요 {s.get('총좋아요', 0):,}, "
        summary_text += f"일간조회 +{s.get('일간조회수', 0):,}, "
        fg = int(s.get('팔로워증감', 0))
        fg_str = f"+{fg}" if fg >= 0 else str(fg)
        summary_text += f"팔로워 {s.get('팔로워수', 0)}({fg_str}), "
        summary_text += f"평균참여율 {s.get('평균참여율(%)', 0)}%\n"

    # Top 게시물 (각 채널 상위 3개)
    top_posts_text = ""
    for ch_key, posts in channel_posts.items():
        ch_name = {"instagram": "Instagram", "youtube": "YouTube", "tiktok": "TikTok"}.get(ch_key, ch_key)
        sorted_posts = sorted(posts, key=lambda p: p.get("조회수", 0) if isinstance(p.get("조회수"), (int, float)) else 0, reverse=True)[:3]
        top_posts_text += f"\n[{ch_name} Top 3]\n"
        for i, p in enumerate(sorted_posts, 1):
            views = p.get("조회수", 0)
            likes = p.get("좋아요", 0)
            grade = p.get("등급", "-")
            caption = p.get("캡션", "")[:40]
            top_posts_text += f"{i}. \"{caption}\" - 조회{views:,}, 좋아요{likes:,}, 등급{grade}\n"

    # 이상치
    anomaly_text = ""
    if anomalies:
        anomaly_text = "\n[평균 대비 급상승 게시물]\n"
        for a in anomalies[:3]:
            anomaly_text += f"- [{a['채널']}] \"{a['캡션'][:30]}\" 평균의 {a['평균대비']}배 ({a['조회수']:,}회)\n"

    prompt = f"""다음은 한국 뷰티 크리에이터 "유아연"의 오늘 SNS 성과 데이터입니다.

## 채널별 요약
{summary_text}

## 주요 게시물
{top_posts_text}
{anomaly_text}

위 데이터를 분석해서 한국어로 다음 JSON 형식으로만 답변해주세요. 설명 없이 JSON만 출력해주세요:

{{
  "요약": "2-3문장으로 오늘의 성과를 요약. 구체적 수치 포함. 예: '오늘 Instagram 조회수가 어제보다 30% 증가했고, 특히 릴스 콘텐츠가 강세를 보였어요.'",
  "추천": [
    "향후 콘텐츠 전략에 대한 구체적 추천 1 (1문장)",
    "향후 콘텐츠 전략에 대한 구체적 추천 2",
    "향후 콘텐츠 전략에 대한 구체적 추천 3"
  ],
  "주의": [
    "주의가 필요한 지표나 하락세 1 (1문장)",
    "주의가 필요한 지표나 하락세 2"
  ]
}}

뷰티/콘텐츠 마케팅 관점에서 실용적이고 구체적인 조언을 주세요. 막연한 말은 피해주세요."""

    result_text = _call_claude(prompt)
    if not result_text:
        return {
            "요약": "AI 분석을 일시적으로 사용할 수 없습니다.",
            "추천": [],
            "주의": [],
        }

    # JSON 파싱
    try:
        # JSON 블록 추출
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]
        result_text = result_text.strip()

        data = json.loads(result_text)
        return {
            "요약": data.get("요약", ""),
            "추천": data.get("추천", []) if isinstance(data.get("추천"), list) else [],
            "주의": data.get("주의", []) if isinstance(data.get("주의"), list) else [],
        }
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"AI 응답 파싱 실패: {e}")
        return {
            "요약": result_text[:300],
            "추천": [],
            "주의": [],
        }


def generate_content_recommendations(channel_posts, top_growing):
    """성과 좋은 콘텐츠 패턴을 분석하여 다음 콘텐츠 아이디어를 추천합니다.

    Returns:
        List[str] - 추천 콘텐츠 아이디어
    """
    if not ANTHROPIC_API_KEY:
        return []

    # 상위 성과 게시물 추출
    all_posts = []
    for ch_key, posts in channel_posts.items():
        for p in posts:
            views = p.get("조회수", 0)
            if isinstance(views, (int, float)) and views > 0:
                all_posts.append({
                    "채널": ch_key,
                    "캡션": p.get("캡션", ""),
                    "조회수": views,
                    "등급": p.get("등급", "C"),
                })

    if not all_posts:
        return []

    all_posts.sort(key=lambda p: p["조회수"], reverse=True)
    top_posts = all_posts[:10]

    posts_text = "\n".join([f"- [{p['채널']}] \"{p['캡션'][:40]}\" 조회{p['조회수']:,} ({p['등급']}급)" for p in top_posts])

    prompt = f"""다음은 한국 뷰티 크리에이터 "유아연"의 최근 성과가 좋은 SNS 콘텐츠들입니다.

{posts_text}

이 데이터를 기반으로 **다음에 만들면 좋을 콘텐츠 아이디어 5개**를 추천해주세요.
- 성과 좋은 콘텐츠의 공통 패턴을 분석해서
- 구체적이고 실행 가능한 주제로
- 각 아이디어는 1문장(30자 내외)로

JSON 배열 형식으로만 답변해주세요:
["아이디어1", "아이디어2", "아이디어3", "아이디어4", "아이디어5"]"""

    result = _call_claude(prompt, max_tokens=500)
    if not result:
        return []

    try:
        if "```" in result:
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
            result = result.split("```")[0] if "```" in result else result
        result = result.strip()
        ideas = json.loads(result)
        if isinstance(ideas, list):
            return ideas[:5]
    except (json.JSONDecodeError, IndexError):
        pass
    return []
