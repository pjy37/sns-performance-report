"""슬랙 웹훅 메시지 전송 - SNS 성과 리포트

슬랙 Incoming Webhook 설정 방법:
1. https://api.slack.com/apps 접속
2. 'Create New App' → 'From scratch' 선택
3. 앱 이름 입력 (예: SNS성과리포트봇), 워크스페이스 선택
4. 좌측 메뉴 'Incoming Webhooks' → 활성화
5. 'Add New Webhook to Workspace' 클릭 → 채널 선택
6. 생성된 Webhook URL을 .env의 SLACK_WEBHOOK_URL에 입력
"""

import json
import requests
from config import SLACK_WEBHOOK_URL


def _format_number(n):
    """숫자를 읽기 쉬운 형식으로 포맷합니다."""
    if not isinstance(n, (int, float)):
        return str(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    else:
        return f"{n:,.0f}"


def send_slack_report(analysis):
    """분석 결과를 슬랙에 전송합니다.

    Args:
        analysis: Dict - generate_analysis()의 반환값
    """
    if not SLACK_WEBHOOK_URL or "여기에" in SLACK_WEBHOOK_URL:
        print("  [Slack] 웹훅 URL이 설정되지 않았습니다.")
        return False

    date = analysis.get("날짜", "")
    channels = analysis.get("채널별", [])
    top_growing = analysis.get("성장_TOP5", [])

    channel_icons = {"Instagram": ":camera:", "YouTube": ":movie_camera:", "TikTok": ":musical_note:"}

    lines = []
    lines.append(f"*:bar_chart: SNS 성과 일일 리포트 ({date})*")
    lines.append("")
    lines.append("*━━━ 전체 요약 ━━━*")

    for ch in channels:
        channel = ch.get("채널", "")
        icon = channel_icons.get(channel, ":pushpin:")
        posts = ch.get("총게시물수", 0)
        views = _format_number(ch.get("총조회수", 0))
        views_change = ch.get("조회수_변화", "-")
        engagement = ch.get("평균참여율(%)", 0)
        followers = _format_number(ch.get("팔로워수", 0))
        follower_change = ch.get("팔로워_변화", "-")

        lines.append(
            f"{icon} *{channel}*: 게시물 {posts}개 | "
            f"조회 {views} ({views_change}) | "
            f"참여율 {engagement}% | "
            f"팔로워 {followers} ({follower_change})"
        )

    if top_growing:
        lines.append("")
        lines.append("*━━━ :fire: Top 5 성장 게시물 (조회수 증가) ━━━*")
        for i, post in enumerate(top_growing, 1):
            channel = post.get("채널", "")
            caption = post.get("캡션", "")
            growth = _format_number(post.get("조회수_증가", 0))
            growth_pct = post.get("증가율(%)", 0)
            lines.append(
                f"{i}. [{channel}] \"{caption}\" +{growth} 조회 (+{growth_pct}%)"
            )

    message = "\n".join(lines)

    payload = {
        "text": message,
        "unfurl_links": False,
        "unfurl_media": False,
    }

    response = requests.post(
        SLACK_WEBHOOK_URL,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 200:
        print("  [Slack] 리포트 전송 완료!")
        return True
    else:
        print(f"  [Slack] 전송 실패: {response.status_code} - {response.text}")
        return False


def send_error_notification(error_msg):
    """에러 발생 시 슬랙에 알림을 보냅니다."""
    if not SLACK_WEBHOOK_URL or "여기에" in SLACK_WEBHOOK_URL:
        return

    payload = {
        "text": f":warning: *SNS 성과 리포트 자동화 에러*\n{error_msg}",
    }

    requests.post(
        SLACK_WEBHOOK_URL,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
