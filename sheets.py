"""구글시트 연동 - 게시물별 성과 데이터 기록 및 조회 (OAuth 인증)"""

import gspread
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import (
    GOOGLE_SHEET_ID, GOOGLE_SHEETS_CLIENT_ID, GOOGLE_SHEETS_CLIENT_SECRET,
    GOOGLE_SHEETS_REFRESH_TOKEN, SHEET_NAMES, POST_HEADERS, SUMMARY_HEADERS,
    CROSS_HEADERS,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_client():
    """OAuth로 구글시트 클라이언트를 생성합니다."""
    creds = Credentials(
        token=None,
        refresh_token=GOOGLE_SHEETS_REFRESH_TOKEN,
        client_id=GOOGLE_SHEETS_CLIENT_ID,
        client_secret=GOOGLE_SHEETS_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return gspread.authorize(creds)


def _get_or_create_worksheet(spreadsheet, sheet_name, headers):
    """시트가 없으면 생성하고, 헤더가 없으면 추가합니다."""
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=5000, cols=len(headers))
        worksheet.append_row(headers)
        print(f"    '{sheet_name}' 시트 생성 완료")
    else:
        existing = worksheet.row_values(1)
        if not existing:
            worksheet.append_row(headers)
    return worksheet


def write_post_data(channel_key, posts):
    """채널별 시트에 게시물별 성과 데이터를 기록합니다.

    Args:
        channel_key: "instagram", "youtube", "tiktok"
        posts: List[Dict] - 게시물별 성과 데이터
    """
    if not posts:
        return

    if not GOOGLE_SHEET_ID:
        print("  [Sheets] 구글시트 ID가 설정되지 않았습니다.")
        return

    client = _get_client()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    sheet_name = SHEET_NAMES.get(channel_key, channel_key)
    worksheet = _get_or_create_worksheet(spreadsheet, sheet_name, POST_HEADERS)

    rows = []
    for post in posts:
        row = [
            post.get("날짜", ""),
            post.get("게시물ID", ""),
            post.get("캡션", ""),
            post.get("게시일", ""),
            post.get("타입", ""),
            post.get("링크", ""),
            post.get("조회수", 0),
            post.get("좋아요", 0),
            post.get("댓글", 0),
            post.get("공유", 0),
            post.get("저장", "-"),
            post.get("팔로워유입", "-"),
            post.get("참여율(%)", 0),
        ]
        rows.append(row)

    if rows:
        worksheet.append_rows(rows)
        print(f"  [Sheets] {sheet_name} 시트에 {len(rows)}행 기록 완료")


def write_summary(summaries):
    """요약 시트에 채널별 합산 데이터를 기록합니다.

    Args:
        summaries: List[Dict] - 채널별 요약 데이터
    """
    if not summaries or not GOOGLE_SHEET_ID:
        return

    client = _get_client()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    worksheet = _get_or_create_worksheet(spreadsheet, SHEET_NAMES["summary"], SUMMARY_HEADERS)

    rows = []
    for s in summaries:
        row = [
            s.get("날짜", ""),
            s.get("채널", ""),
            s.get("총게시물수", 0),
            s.get("총조회수", 0),
            s.get("총좋아요", 0),
            s.get("총댓글", 0),
            s.get("총공유", 0),
            s.get("평균참여율(%)", 0),
            s.get("팔로워수", 0),
        ]
        rows.append(row)

    if rows:
        worksheet.append_rows(rows)
        print(f"  [Sheets] 요약 시트에 {len(rows)}행 기록 완료")


def write_cross_comparison(cross_data):
    """크로스비교 시트에 동일 콘텐츠의 채널별 성과를 기록합니다.

    Args:
        cross_data: List[Dict] - 크로스 비교 데이터
    """
    if not cross_data or not GOOGLE_SHEET_ID:
        return

    client = _get_client()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    worksheet = _get_or_create_worksheet(spreadsheet, SHEET_NAMES["cross"], CROSS_HEADERS)

    rows = []
    for item in cross_data:
        row = [
            item.get("날짜", ""),
            item.get("게시일", ""),
            item.get("캡션", ""),
            item.get("IG조회수", "-"),
            item.get("IG좋아요", "-"),
            item.get("IG참여율(%)", "-"),
            item.get("YT조회수", "-"),
            item.get("YT좋아요", "-"),
            item.get("YT참여율(%)", "-"),
            item.get("TT조회수", "-"),
            item.get("TT좋아요", "-"),
            item.get("TT참여율(%)", "-"),
            item.get("총조회수", 0),
            item.get("최고채널", "-"),
        ]
        rows.append(row)

    if rows:
        worksheet.append_rows(rows)
        print(f"  [Sheets] 크로스비교 시트에 {len(rows)}행 기록 완료")


def get_previous_data(channel_key, target_date):
    """전일 데이터를 시트에서 읽어옵니다.

    Args:
        channel_key: "instagram", "youtube", "tiktok" 또는 "summary"
        target_date: 조회할 날짜 (YYYY-MM-DD)

    Returns:
        List[Dict] - 해당 날짜의 데이터
    """
    if not GOOGLE_SHEET_ID:
        return []

    try:
        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

        if channel_key == "summary":
            sheet_name = SHEET_NAMES["summary"]
        else:
            sheet_name = SHEET_NAMES.get(channel_key, channel_key)

        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            return []

        all_data = worksheet.get_all_records()
        return [row for row in all_data if str(row.get("날짜", "")) == target_date]

    except Exception as e:
        print(f"  [Sheets] 전일 데이터 조회 실패: {e}")
        return []


def get_recent_data(channel_key, days=7):
    """최근 N일간 데이터를 시트에서 읽어옵니다 (HTML 보고서용).

    Args:
        channel_key: "instagram", "youtube", "tiktok" 또는 "summary"
        days: 최근 일수

    Returns:
        List[Dict] - 최근 데이터
    """
    if not GOOGLE_SHEET_ID:
        return []

    try:
        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

        if channel_key == "summary":
            sheet_name = SHEET_NAMES["summary"]
        else:
            sheet_name = SHEET_NAMES.get(channel_key, channel_key)

        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            return []

        all_data = worksheet.get_all_records()

        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return [row for row in all_data if str(row.get("날짜", "")) >= cutoff]

    except Exception as e:
        print(f"  [Sheets] 최근 데이터 조회 실패: {e}")
        return []
