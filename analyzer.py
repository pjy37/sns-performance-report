"""전일 대비 변화량 계산 및 성과 분석"""

from config import today


def _calc_change(current, previous):
    """변화율을 계산합니다."""
    if previous == 0:
        return 0 if current == 0 else 100.0
    return round((current - previous) / previous * 100, 1)


def _change_indicator(change_pct):
    """변화율에 따른 화살표 표시를 반환합니다."""
    if change_pct > 0:
        return f"▲{change_pct}%"
    elif change_pct < 0:
        return f"▼{change_pct}%"
    else:
        return "- 0%"


def _safe_num(val):
    """시트에서 읽은 값을 안전하게 숫자로 변환합니다."""
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str) and val not in ("-", ""):
        try:
            return float(val)
        except (ValueError, TypeError):
            pass
    return 0


def calculate_summary_changes(today_summary, prev_summary):
    """채널별 요약의 전일 대비 변화량을 계산합니다."""
    if not prev_summary:
        return {
            "총조회수": today_summary.get("총조회수", 0),
            "총좋아요": today_summary.get("총좋아요", 0),
            "평균참여율(%)": today_summary.get("평균참여율(%)", 0),
            "팔로워수": today_summary.get("팔로워수", 0),
            "조회수_변화": "데이터 없음",
            "좋아요_변화": "데이터 없음",
            "참여율_변화": "데이터 없음",
            "팔로워_변화": "데이터 없음",
        }

    views_change = _calc_change(
        today_summary.get("총조회수", 0),
        _safe_num(prev_summary.get("총조회수", 0)),
    )
    likes_change = _calc_change(
        today_summary.get("총좋아요", 0),
        _safe_num(prev_summary.get("총좋아요", 0)),
    )
    engagement_change = _calc_change(
        today_summary.get("평균참여율(%)", 0),
        _safe_num(prev_summary.get("평균참여율(%)", 0)),
    )
    followers_change = (
        today_summary.get("팔로워수", 0)
        - int(_safe_num(prev_summary.get("팔로워수", 0)))
    )

    return {
        "총조회수": today_summary.get("총조회수", 0),
        "총좋아요": today_summary.get("총좋아요", 0),
        "평균참여율(%)": today_summary.get("평균참여율(%)", 0),
        "팔로워수": today_summary.get("팔로워수", 0),
        "조회수_변화": _change_indicator(views_change),
        "좋아요_변화": _change_indicator(likes_change),
        "참여율_변화": _change_indicator(engagement_change),
        "팔로워_변화": f"+{followers_change}" if followers_change >= 0 else str(followers_change),
    }


def find_top_growing_posts(today_posts, prev_posts, top_n=5):
    """조회수 증가가 가장 큰 게시물 Top N을 찾습니다.

    Args:
        today_posts: Dict[channel_key, List[Dict]] - 오늘 채널별 게시물 데이터
        prev_posts: Dict[channel_key, List[Dict]] - 전일 채널별 게시물 데이터
        top_n: 상위 N개

    Returns:
        List[Dict] - 상위 성장 게시물
    """
    channel_labels = {"instagram": "IG", "youtube": "YT", "tiktok": "TT"}

    # 전일 데이터를 게시물ID로 인덱싱
    prev_by_id = {}
    for channel_key, posts in prev_posts.items():
        for post in posts:
            pid = str(post.get("게시물ID", ""))
            if pid:
                prev_by_id[pid] = post

    growth_list = []
    for channel_key, posts in today_posts.items():
        label = channel_labels.get(channel_key, channel_key)
        for post in posts:
            pid = str(post.get("게시물ID", ""))
            current_views = _safe_num(post.get("조회수", 0))
            prev_post = prev_by_id.get(pid)

            if prev_post:
                prev_views = _safe_num(prev_post.get("조회수", 0))
                growth = current_views - prev_views
                growth_pct = _calc_change(current_views, prev_views)
            else:
                growth = current_views
                growth_pct = 100.0 if current_views > 0 else 0

            if growth > 0:
                growth_list.append({
                    "채널": label,
                    "캡션": post.get("캡션", ""),
                    "조회수_증가": int(growth),
                    "증가율(%)": growth_pct,
                    "현재_조회수": int(current_views),
                })

    growth_list.sort(key=lambda x: x["조회수_증가"], reverse=True)
    return growth_list[:top_n]


def build_cross_comparison(channel_posts):
    """동일 게시일 콘텐츠를 그룹핑하여 크로스 비교 데이터를 생성합니다.

    Args:
        channel_posts: Dict[channel_key, List[Dict]] - 채널별 게시물 데이터

    Returns:
        List[Dict] - 크로스 비교 데이터
    """
    # 게시일별로 그룹핑
    by_date = {}
    for channel_key, posts in channel_posts.items():
        for post in posts:
            pub_date = post.get("게시일", "")
            if not pub_date:
                continue
            if pub_date not in by_date:
                by_date[pub_date] = {}
            by_date[pub_date][channel_key] = post

    cross_data = []
    for pub_date in sorted(by_date.keys(), reverse=True):
        channels = by_date[pub_date]

        # 최소 2개 채널에 같은 날 올린 콘텐츠만 비교
        if len(channels) < 2:
            continue

        ig = channels.get("instagram", {})
        yt = channels.get("youtube", {})
        tt = channels.get("tiktok", {})

        # 캡션은 아무 채널에서나 가져옴
        caption = ig.get("캡션") or yt.get("캡션") or tt.get("캡션") or ""

        ig_views = _safe_num(ig.get("조회수", 0))
        yt_views = _safe_num(yt.get("조회수", 0))
        tt_views = _safe_num(tt.get("조회수", 0))
        total_views = ig_views + yt_views + tt_views

        # 최고 채널 결정
        best = max(
            [("Instagram", ig_views), ("YouTube", yt_views), ("TikTok", tt_views)],
            key=lambda x: x[1],
        )

        item = {
            "날짜": today,
            "게시일": pub_date,
            "캡션": caption,
            "IG조회수": int(ig_views) if ig else "-",
            "IG좋아요": _safe_num(ig.get("좋아요", 0)) if ig else "-",
            "IG참여율(%)": _safe_num(ig.get("참여율(%)", 0)) if ig else "-",
            "YT조회수": int(yt_views) if yt else "-",
            "YT좋아요": _safe_num(yt.get("좋아요", 0)) if yt else "-",
            "YT참여율(%)": _safe_num(yt.get("참여율(%)", 0)) if yt else "-",
            "TT조회수": int(tt_views) if tt else "-",
            "TT좋아요": _safe_num(tt.get("좋아요", 0)) if tt else "-",
            "TT참여율(%)": _safe_num(tt.get("참여율(%)", 0)) if tt else "-",
            "총조회수": int(total_views),
            "최고채널": best[0],
        }
        cross_data.append(item)

    return cross_data


def generate_analysis(channel_summaries, prev_channel_summaries, channel_posts, prev_posts):
    """전체 분석 결과를 생성합니다.

    Args:
        channel_summaries: List[Dict] - 오늘 채널별 요약
        prev_channel_summaries: List[Dict] - 전일 채널별 요약
        channel_posts: Dict[channel_key, List[Dict]] - 오늘 채널별 게시물
        prev_posts: Dict[channel_key, List[Dict]] - 전일 채널별 게시물

    Returns:
        Dict - 분석 결과
    """
    prev_map = {s.get("채널", ""): s for s in prev_channel_summaries}

    # 채널별 분석
    channel_analysis = []
    for summary in channel_summaries:
        channel = summary.get("채널", "")
        prev = prev_map.get(channel, {})
        analysis = calculate_summary_changes(summary, prev)
        analysis["채널"] = channel
        analysis["총게시물수"] = summary.get("총게시물수", 0)
        channel_analysis.append(analysis)

    # Top 5 성장 게시물
    top_growing = find_top_growing_posts(channel_posts, prev_posts)

    # 크로스 플랫폼 비교
    cross_comparison = build_cross_comparison(channel_posts)

    return {
        "날짜": today,
        "채널별": channel_analysis,
        "성장_TOP5": top_growing,
        "크로스비교": cross_comparison,
    }
