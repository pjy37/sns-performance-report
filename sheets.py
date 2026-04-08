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

    같은 날짜+채널 조합이 이미 있으면 덮어쓰고, 없으면 추가합니다.

    Args:
        summaries: List[Dict] - 채널별 요약 데이터
    """
    if not summaries or not GOOGLE_SHEET_ID:
        return

    client = _get_client()
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    worksheet = _get_or_create_worksheet(spreadsheet, SHEET_NAMES["summary"], SUMMARY_HEADERS)

    # 기존 데이터에서 오늘 날짜 행 삭제 (중복 방지)
    today_date = summaries[0].get("날짜", "")
    if today_date:
        all_vals = worksheet.get_all_values()
        rows_to_delete = []
        for i, row in enumerate(all_vals):
            if i == 0:
                continue  # 헤더 스킵
            if row[0] == today_date:
                rows_to_delete.append(i + 1)  # 1-based index
        # 뒤에서부터 삭제 (인덱스 꼬임 방지)
        for row_idx in reversed(rows_to_delete):
            worksheet.delete_rows(row_idx)

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
            s.get("일간조회수", 0),
            s.get("일간좋아요", 0),
            s.get("일간댓글", 0),
            s.get("팔로워증감", 0),
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


def _safe_get_all_records(worksheet, headers=None):
    """헤더 중복 문제를 우회하여 시트 데이터를 읽습니다."""
    all_vals = worksheet.get_all_values()
    if len(all_vals) <= 1:
        return []

    # 헤더 결정: 파라미터로 받거나 첫 번째 행 사용
    header_row = headers or all_vals[0]
    # 빈 헤더 처리
    header_row = [h if h else f"_col{i}" for i, h in enumerate(header_row)]

    records = []
    for row in all_vals[1:]:
        record = {}
        for i, h in enumerate(header_row):
            record[h] = row[i] if i < len(row) else ""
        records.append(record)
    return records


def get_previous_data(channel_key, target_date):
    """전일 데이터를 시트에서 읽어옵니다."""
    if not GOOGLE_SHEET_ID:
        return []

    try:
        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

        if channel_key == "summary":
            sheet_name = SHEET_NAMES["summary"]
            headers = SUMMARY_HEADERS
        else:
            sheet_name = SHEET_NAMES.get(channel_key, channel_key)
            headers = POST_HEADERS

        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            return []

        all_data = _safe_get_all_records(worksheet, headers)
        return [row for row in all_data if str(row.get("날짜", "")) == target_date]

    except Exception as e:
        print(f"  [Sheets] 전일 데이터 조회 실패: {e}")
        return []


def get_recent_data(channel_key, days=7):
    """최근 N일간 데이터를 시트에서 읽어옵니다 (HTML 보고서용)."""
    if not GOOGLE_SHEET_ID:
        return []

    try:
        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

        if channel_key == "summary":
            sheet_name = SHEET_NAMES["summary"]
            headers = SUMMARY_HEADERS
        else:
            sheet_name = SHEET_NAMES.get(channel_key, channel_key)
            headers = POST_HEADERS

        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            return []

        all_data = _safe_get_all_records(worksheet, headers)

        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return [row for row in all_data if str(row.get("날짜", "")) >= cutoff]

    except Exception as e:
        print(f"  [Sheets] 최근 데이터 조회 실패: {e}")
        return []


# ─────────────────────────────────────────
#  사용자 정의 시트 (콘텐츠 DB / 주간 / 월간) 자동 업데이트
# ─────────────────────────────────────────

def _safe_int(v):
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        try:
            return int(v.replace(",", "").replace("+", ""))
        except (ValueError, TypeError):
            return 0
    return 0


def _safe_float(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.replace(",", "").replace("%", "").replace("+", ""))
        except (ValueError, TypeError):
            return 0.0
    return 0.0


def update_content_db(channel_posts):
    """'콘텐츠 DB' 시트에 게시물별 데이터를 업데이트합니다.
    같은 (날짜, 플랫폼, 콘텐츠명) 키는 덮어쓰고 새 항목은 추가합니다.

    헤더: 업로드 날짜 | 플랫폼 | 콘텐츠명 | 조회수 | 좋아요 | 저장·보관·공유 |
          팔로워 증가 | 좋아요율(%) | 저장율(%) | 등급(자동) | 주제 태그 | 포맷 | 메모
    """
    if not GOOGLE_SHEET_ID:
        return

    try:
        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

        try:
            ws = spreadsheet.worksheet("콘텐츠 DB")
        except gspread.exceptions.WorksheetNotFound:
            print("  [Sheets] '콘텐츠 DB' 시트가 없어 자동 업데이트를 건너뜁니다.")
            return

        # 기존 데이터 읽기 (헤더는 1행, 데이터는 2행부터)
        all_vals = ws.get_all_values()
        # 헤더가 row 1에 있는지 확인 (제목이 row 0)
        if len(all_vals) < 2:
            return

        existing_keys = {}  # {(날짜, 플랫폼, 콘텐츠명): row_index}
        for i, row in enumerate(all_vals[2:], start=3):  # 1-based, 데이터 시작 row 3
            if len(row) >= 3:
                key = (row[0], row[1], row[2])
                existing_keys[key] = i

        ch_label = {"instagram": "IG", "youtube": "YT", "tiktok": "TT"}

        new_rows = []
        update_cells = []  # [(row_idx, values_list)]

        for channel_key, posts in channel_posts.items():
            label = ch_label.get(channel_key, channel_key)
            for p in posts:
                pub_date = p.get("게시일", "")
                caption = (p.get("캡션", "") or "")[:50]
                if not pub_date or not caption:
                    continue

                views = _safe_int(p.get("조회수", 0))
                likes = _safe_int(p.get("좋아요", 0))
                saved_raw = p.get("저장", 0)
                saved = _safe_int(saved_raw) if saved_raw != "-" else 0
                shares = _safe_int(p.get("공유", 0))
                save_share = saved + shares
                follows = p.get("팔로워유입", "-")
                follows_str = f"+{follows}" if isinstance(follows, (int, float)) and follows > 0 else (str(follows) if follows != 0 else "-")

                like_rate = round(likes / views * 100, 1) if views > 0 else 0
                save_rate = round(saved / views * 100, 1) if views > 0 else 0
                grade = p.get("등급", "C")

                row_data = [
                    pub_date, label, caption,
                    f"{views:,}", str(likes), str(save_share),
                    follows_str,
                    f"{like_rate}%", f"{save_rate}%", grade,
                    "", "", "",  # 주제태그, 포맷, 메모는 사용자 입력
                ]

                key = (pub_date, label, caption)
                if key in existing_keys:
                    update_cells.append((existing_keys[key], row_data))
                else:
                    new_rows.append(row_data)

        # 기존 행 업데이트 (조회수/좋아요/등급 등 변경된 부분)
        for row_idx, values in update_cells:
            try:
                # A부터 J까지만 업데이트 (주제태그/포맷/메모는 사용자 입력 보존)
                ws.update(f"A{row_idx}:J{row_idx}", [values[:10]])
            except Exception as e:
                print(f"  [Sheets] 콘텐츠 DB 업데이트 오류: {e}")

        # 새 행 추가
        if new_rows:
            ws.append_rows(new_rows, value_input_option="USER_ENTERED")

        print(f"  [Sheets] 콘텐츠 DB: 신규 {len(new_rows)}건, 업데이트 {len(update_cells)}건")

    except Exception as e:
        print(f"  [Sheets] 콘텐츠 DB 자동 업데이트 실패: {e}")


def update_weekly_status(channel_summaries, grade_stats_by_channel, prev_week_summaries=None):
    """'주간 채널 현황' 시트에 이번 주 데이터를 업데이트합니다.

    헤더: 기준일 | 주차 | IG팔로워 | IG순증 | YT구독자 | YT순증 | TT팔로워 | TT순증 |
          전체팔로워순증 | 업로드수 | S급수 | A급수 | S급비율 | 전주대비성장율 | 메모
    """
    if not GOOGLE_SHEET_ID:
        return

    try:
        from datetime import datetime, timedelta
        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

        try:
            ws = spreadsheet.worksheet("주간 채널 현황")
        except gspread.exceptions.WorksheetNotFound:
            print("  [Sheets] '주간 채널 현황' 시트가 없어 자동 업데이트를 건너뜁니다.")
            return

        # 이번 주 월요일 계산
        today_dt = datetime.now()
        monday = today_dt - timedelta(days=today_dt.weekday())
        monday_str = monday.strftime("%Y-%m-%d")

        # 주차 계산: ISO 주차 기준으로 해당 월에서 몇 번째 월요일인지
        first_of_month = datetime(monday.year, monday.month, 1)
        # 해당 월의 첫 번째 월요일
        days_to_first_monday = (7 - first_of_month.weekday()) % 7
        first_monday = first_of_month + timedelta(days=days_to_first_monday)
        if monday < first_monday:
            # 이번 주 월요일이 이번 달 첫 월요일보다 전이면 전월 마지막 주
            prev_month = (first_of_month - timedelta(days=1))
            first_of_prev = datetime(prev_month.year, prev_month.month, 1)
            days_to_first_mon_prev = (7 - first_of_prev.weekday()) % 7
            first_monday_prev = first_of_prev + timedelta(days=days_to_first_mon_prev)
            week_num = (monday - first_monday_prev).days // 7 + 1
            week_label = f"{prev_month.month}월 {week_num}주차"
        else:
            week_num = (monday - first_monday).days // 7 + 1
            week_label = f"{monday.month}월 {week_num}주차"

        # 채널별 현재 팔로워
        ig_followers = 0
        yt_followers = 0
        tt_followers = 0
        for s in channel_summaries:
            ch = s.get("채널", "")
            f = _safe_int(s.get("팔로워수", 0))
            if ch == "Instagram":
                ig_followers = f
            elif ch == "YouTube":
                yt_followers = f
            elif ch == "TikTok":
                tt_followers = f

        # 등급 통계
        s_count = sum(stats.get("S", 0) for stats in grade_stats_by_channel.values())
        a_count = sum(stats.get("A", 0) for stats in grade_stats_by_channel.values())
        upload_count = sum(stats.get("S", 0) + stats.get("A", 0) + stats.get("B", 0) + stats.get("C", 0)
                           for stats in grade_stats_by_channel.values())
        s_rate = round(s_count / upload_count * 100, 1) if upload_count else 0

        # 기존 행 찾기:
        # 1순위: 기준일 == monday_str
        # 2순위: 같은 주차 라벨
        # 3순위: 같은 기준일이 비어있고 주차만 일치
        all_vals = ws.get_all_values()
        target_row = None
        for i, row in enumerate(all_vals[2:], start=3):
            if len(row) > 0 and row[0] == monday_str:
                target_row = i
                break
        if target_row is None:
            for i, row in enumerate(all_vals[2:], start=3):
                if len(row) > 1 and row[1] == week_label:
                    target_row = i
                    break

        # 전주 데이터로 순증 계산: 데이터가 있는 가장 최근 행을 찾음
        ig_diff = "-"
        yt_diff = "-"
        tt_diff = "-"
        total_diff = "-"
        prev_week_growth = "-"

        if len(all_vals) > 2:
            last_row = None
            for row in all_vals[2:]:
                # 본인 행 제외하고, IG/YT/TT 팔로워 셀이 채워진 행만
                if (len(row) >= 7 and row[0] and row[0] != monday_str and
                    (row[2] or row[4] or row[6])):
                    last_row = row
            if last_row and len(last_row) >= 7:
                prev_ig = _safe_int(last_row[2])
                prev_yt = _safe_int(last_row[4])
                prev_tt = _safe_int(last_row[6])
                ig_d = ig_followers - prev_ig
                yt_d = yt_followers - prev_yt
                tt_d = tt_followers - prev_tt
                ig_diff = f"+{ig_d}" if ig_d >= 0 else str(ig_d)
                yt_diff = f"+{yt_d}" if yt_d >= 0 else str(yt_d)
                tt_diff = f"+{tt_d}" if tt_d >= 0 else str(tt_d)
                total_d = ig_d + yt_d + tt_d
                total_diff = f"+{total_d}" if total_d >= 0 else str(total_d)

        row_data = [
            monday_str, week_label,
            str(ig_followers), ig_diff,
            str(yt_followers), yt_diff,
            str(tt_followers), tt_diff,
            total_diff,
            str(upload_count), str(s_count), str(a_count),
            f"{s_rate}%", prev_week_growth, "",
        ]

        if target_row:
            # 메모(O열)는 사용자 입력 보존
            ws.update(f"A{target_row}:N{target_row}", [row_data[:14]])
            print(f"  [Sheets] 주간 채널 현황 업데이트 (행 {target_row}, {week_label})")
        else:
            ws.append_row(row_data, value_input_option="USER_ENTERED")
            print(f"  [Sheets] 주간 채널 현황 신규 추가 ({week_label})")

    except Exception as e:
        print(f"  [Sheets] 주간 채널 현황 자동 업데이트 실패: {e}")


def update_monthly_dashboard(channel_summaries, grade_stats_by_channel):
    """'월간 대시보드' 시트에 이번 달 데이터를 업데이트합니다.

    헤더: 월 | IG팔로워 | YT구독자 | TT팔로워 | 전체팔로워합계 |
          월간팔로워순증 | 업로드총수 | S급콘텐츠 | S급비율 | 전월대비성장율
    """
    if not GOOGLE_SHEET_ID:
        return

    try:
        from datetime import datetime
        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

        try:
            ws = spreadsheet.worksheet("월간 대시보드")
        except gspread.exceptions.WorksheetNotFound:
            print("  [Sheets] '월간 대시보드' 시트가 없어 자동 업데이트를 건너뜁니다.")
            return

        today_dt = datetime.now()
        month_str = today_dt.strftime("%Y-%m")

        # 채널별 현재 팔로워
        ig_followers = 0
        yt_followers = 0
        tt_followers = 0
        for s in channel_summaries:
            ch = s.get("채널", "")
            f = _safe_int(s.get("팔로워수", 0))
            if ch == "Instagram":
                ig_followers = f
            elif ch == "YouTube":
                yt_followers = f
            elif ch == "TikTok":
                tt_followers = f

        total_followers = ig_followers + yt_followers + tt_followers
        s_count = sum(stats.get("S", 0) for stats in grade_stats_by_channel.values())
        upload_count = sum(stats.get("S", 0) + stats.get("A", 0) + stats.get("B", 0) + stats.get("C", 0)
                           for stats in grade_stats_by_channel.values())
        s_rate = round(s_count / upload_count * 100, 1) if upload_count else 0

        # 기존 행 찾기 (월 컬럼이 정확히 YYYY-MM 형식인 행만 처리)
        # 'S급 콘텐츠 목록' 등 별도 섹션은 건드리지 않음
        import re
        month_pattern = re.compile(r'^\d{4}-\d{2}$')

        all_vals = ws.get_all_values()
        target_row = None
        prev_total = None
        for i, row in enumerate(all_vals[2:], start=3):
            if len(row) == 0 or not row[0]:
                continue
            if not month_pattern.match(row[0]):
                # 'S급 콘텐츠 목록' 같은 비정상 행을 만나면 중단
                break
            if row[0] == month_str:
                target_row = i
            elif row[0] < month_str and len(row) > 4:
                # 전체 팔로워 합계가 유효한 값이면 prev_total 업데이트
                val = row[4]
                if val and val not in ("-", ""):
                    try:
                        prev_total = int(val.replace(",", ""))
                    except (ValueError, AttributeError):
                        pass

        monthly_diff = "-"
        if prev_total is not None:
            d = total_followers - prev_total
            monthly_diff = f"+{d}" if d >= 0 else str(d)

        row_data = [
            month_str,
            str(ig_followers), str(yt_followers), str(tt_followers),
            str(total_followers), monthly_diff,
            str(upload_count), str(s_count),
            f"{s_rate}%", "-",
        ]

        if target_row:
            ws.update(f"A{target_row}:J{target_row}", [row_data])
            print(f"  [Sheets] 월간 대시보드 업데이트 ({month_str})")
        else:
            ws.append_row(row_data, value_input_option="USER_ENTERED")
            print(f"  [Sheets] 월간 대시보드 신규 추가 ({month_str})")

    except Exception as e:
        print(f"  [Sheets] 월간 대시보드 자동 업데이트 실패: {e}")


def get_weekly_status_data():
    """주간 채널 현황 시트의 데이터를 읽어옵니다.
    실제 팔로워 데이터가 있는 행만 반환합니다 (빈 행은 제외).
    """
    if not GOOGLE_SHEET_ID:
        return []
    try:
        import re
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')

        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        ws = spreadsheet.worksheet("주간 채널 현황")
        all_vals = ws.get_all_values()
        if len(all_vals) < 3:
            return []

        result = []
        for row in all_vals[2:]:
            # 기준일이 YYYY-MM-DD 형식이 아니면 스킵
            if len(row) < 13 or not row[0] or not date_pattern.match(row[0]):
                continue

            # 팔로워 데이터가 모두 비어있는 미래 주는 제외
            ig_raw = row[2] if len(row) > 2 else ""
            yt_raw = row[4] if len(row) > 4 else ""
            tt_raw = row[6] if len(row) > 6 else ""
            if not (ig_raw or yt_raw or tt_raw):
                continue

            result.append({
                "기준일": row[0],
                "주차": row[1],
                "IG팔로워": _safe_int(row[2]),
                "IG순증": row[3] or "-",
                "YT구독자": _safe_int(row[4]),
                "YT순증": row[5] or "-",
                "TT팔로워": _safe_int(row[6]),
                "TT순증": row[7] or "-",
                "전체팔로워순증": row[8] or "-",
                "업로드수": _safe_int(row[9]),
                "S급수": _safe_int(row[10]),
                "A급수": _safe_int(row[11]),
                "S급비율": row[12] or "0%",
            })
        return result
    except Exception as e:
        print(f"  [Sheets] 주간 채널 현황 조회 실패: {e}")
        return []


def get_monthly_dashboard_data():
    """월간 대시보드 시트의 데이터를 읽어옵니다.
    실제 데이터가 있는 행만 반환합니다 (미래 월/별도 섹션 제외).
    """
    if not GOOGLE_SHEET_ID:
        return []
    try:
        import re
        month_pattern = re.compile(r'^\d{4}-\d{2}$')

        client = _get_client()
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        ws = spreadsheet.worksheet("월간 대시보드")
        all_vals = ws.get_all_values()
        if len(all_vals) < 3:
            return []

        result = []
        for row in all_vals[2:]:
            # 월 컬럼이 YYYY-MM 형식이 아니면 (S급 콘텐츠 목록 등) 중단
            if len(row) < 9 or not row[0]:
                continue
            if not month_pattern.match(row[0]):
                # 별도 섹션 시작이면 중단
                break

            # 전체 팔로워 합계가 비어있거나 '-' 인 미래 월은 제외
            total = row[4] if len(row) > 4 else ""
            if not total or total in ("-", "0"):
                continue

            result.append({
                "월": row[0],
                "IG팔로워": _safe_int(row[1]),
                "YT구독자": _safe_int(row[2]),
                "TT팔로워": _safe_int(row[3]),
                "전체팔로워합계": _safe_int(row[4]),
                "월간팔로워순증": row[5] or "-",
                "업로드총수": _safe_int(row[6]),
                "S급콘텐츠": _safe_int(row[7]),
                "S급비율": row[8] or "0%",
            })
        return result
    except Exception as e:
        print(f"  [Sheets] 월간 대시보드 조회 실패: {e}")
        return []
