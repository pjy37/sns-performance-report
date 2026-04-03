"""SNS 성과 자동화 - 환경변수 및 상수 설정"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# 날짜 설정
today = datetime.now().strftime("%Y-%m-%d")
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

# ── Instagram / Meta ──
META_PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
META_API_VERSION = "v21.0"

# ── YouTube ──
YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID", "")

# ── TikTok ──
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "")
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN", "")

# ── Google Sheets ──
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SHEETS_CLIENT_ID = os.getenv("GOOGLE_SHEETS_CLIENT_ID", "")
GOOGLE_SHEETS_CLIENT_SECRET = os.getenv("GOOGLE_SHEETS_CLIENT_SECRET", "")
GOOGLE_SHEETS_REFRESH_TOKEN = os.getenv("GOOGLE_SHEETS_REFRESH_TOKEN", "")

# ── Slack ──
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# ── 설정 ──
POST_MAX_AGE_DAYS = int(os.getenv("POST_MAX_AGE_DAYS", "90"))

# 시트 이름
SHEET_NAMES = {
    "instagram": "Instagram",
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "summary": "요약",
    "cross": "크로스비교",
}

# 채널별 시트 컬럼 헤더
POST_HEADERS = [
    "날짜", "게시물ID", "캡션", "게시일", "타입", "링크",
    "조회수", "좋아요", "댓글", "공유", "저장", "팔로워유입", "참여율(%)",
]

# 요약 시트 컬럼 헤더
SUMMARY_HEADERS = [
    "날짜", "채널", "총게시물수", "총조회수", "총좋아요",
    "총댓글", "총공유", "평균참여율(%)", "팔로워수",
    "일간조회수", "일간좋아요", "일간댓글", "팔로워증감",
]

# 크로스비교 시트 컬럼 헤더
CROSS_HEADERS = [
    "날짜", "게시일", "캡션",
    "IG조회수", "IG좋아요", "IG참여율(%)",
    "YT조회수", "YT좋아요", "YT참여율(%)",
    "TT조회수", "TT좋아요", "TT참여율(%)",
    "총조회수", "최고채널",
]
