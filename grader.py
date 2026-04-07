"""콘텐츠 등급 산정 및 이상치 감지"""

from config import GRADE_THRESHOLDS, ANOMALY_THRESHOLD


def _safe_num(v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v.replace(",", ""))
        except (ValueError, TypeError):
            pass
    return 0


def calculate_grade(post):
    """게시물의 등급(S/A/B/C)을 계산합니다.

    Args:
        post: Dict - 게시물 데이터 (조회수, 좋아요, 저장 포함)

    Returns:
        Dict - {등급, 좋아요율, 저장율}
    """
    views = _safe_num(post.get("조회수", 0))
    likes = _safe_num(post.get("좋아요", 0))
    saved_raw = post.get("저장", 0)
    saved = _safe_num(saved_raw) if saved_raw != "-" else 0

    if views <= 0:
        return {"등급": "-", "좋아요율": 0, "저장율": 0}

    like_rate = round(likes / views * 100, 2)
    save_rate = round(saved / views * 100, 2) if saved > 0 else 0

    # 등급 판정
    if save_rate >= GRADE_THRESHOLDS["S"]["save_rate"] and like_rate >= GRADE_THRESHOLDS["S"]["like_rate"]:
        grade = "S"
    elif save_rate >= GRADE_THRESHOLDS["A"]["save_rate"] and like_rate >= GRADE_THRESHOLDS["A"]["like_rate"]:
        grade = "A"
    elif like_rate >= GRADE_THRESHOLDS["B"]["like_rate"]:
        grade = "B"
    else:
        grade = "C"

    return {"등급": grade, "좋아요율": like_rate, "저장율": save_rate}


def apply_grades(posts):
    """게시물 리스트에 등급 정보를 추가합니다."""
    for post in posts:
        grade_info = calculate_grade(post)
        post["등급"] = grade_info["등급"]
        post["좋아요율(%)"] = grade_info["좋아요율"]
        post["저장율(%)"] = grade_info["저장율"]
    return posts


def detect_anomalies(channel_posts):
    """채널별 이상치 게시물을 감지합니다.

    평균 조회수 대비 ANOMALY_THRESHOLD 배 이상인 게시물을 찾습니다.

    Args:
        channel_posts: Dict[channel_key, List[Dict]]

    Returns:
        List[Dict] - 이상치 게시물 리스트
    """
    anomalies = []

    for channel_key, posts in channel_posts.items():
        if len(posts) < 3:  # 최소 3개 이상이어야 이상치 판단 의미 있음
            continue

        views_list = [_safe_num(p.get("조회수", 0)) for p in posts]
        if not views_list:
            continue

        avg_views = sum(views_list) / len(views_list)
        if avg_views == 0:
            continue

        for post in posts:
            views = _safe_num(post.get("조회수", 0))
            if views >= avg_views * ANOMALY_THRESHOLD:
                ratio = round(views / avg_views, 1)
                anomalies.append({
                    "채널": {"instagram": "Instagram", "youtube": "YouTube", "tiktok": "TikTok"}.get(channel_key, channel_key),
                    "게시물ID": post.get("게시물ID", ""),
                    "캡션": post.get("캡션", ""),
                    "링크": post.get("링크", ""),
                    "썸네일": post.get("썸네일", ""),
                    "조회수": int(views),
                    "평균대비": ratio,
                    "타입": "초과성과",  # outperform
                })

    # 평균 대비 배수 내림차순
    anomalies.sort(key=lambda x: x["평균대비"], reverse=True)
    return anomalies[:10]


def calculate_channel_grade_stats(posts):
    """채널별 등급 분포를 계산합니다.

    Returns:
        Dict - {S: 개수, A: 개수, B: 개수, C: 개수, S비율: %, ...}
    """
    if not posts:
        return {"S": 0, "A": 0, "B": 0, "C": 0, "S비율": 0, "A비율": 0}

    stats = {"S": 0, "A": 0, "B": 0, "C": 0}
    for p in posts:
        grade = p.get("등급", "C")
        if grade in stats:
            stats[grade] += 1

    total = len(posts)
    stats["S비율"] = round(stats["S"] / total * 100, 1) if total else 0
    stats["A비율"] = round(stats["A"] / total * 100, 1) if total else 0
    stats["SA합계"] = stats["S"] + stats["A"]
    stats["SA비율"] = round(stats["SA합계"] / total * 100, 1) if total else 0

    return stats
