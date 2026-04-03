"""TikTok 영상별 성과 수집 (Display API v2)"""

import logging
import os
from datetime import datetime, timedelta

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import set_key

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET,
    TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN,
    POST_MAX_AGE_DAYS, today,
)

logger = logging.getLogger("sns_performance")

API_BASE = "https://open.tiktokapis.com/v2"

# 모듈 레벨에서 토큰 관리
_current_token = TIKTOK_ACCESS_TOKEN


def _refresh_access_token():
    """리프레시 토큰으로 액세스 토큰을 갱신합니다."""
    global _current_token

    if not TIKTOK_REFRESH_TOKEN:
        logger.warning("TIKTOK_REFRESH_TOKEN이 없어 토큰 갱신을 건너뜁니다.")
        return _current_token

    print("  [TikTok] 액세스 토큰 갱신 중...")
    resp = requests.post(
        f"{API_BASE}/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": TIKTOK_CLIENT_KEY,
            "client_secret": TIKTOK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": TIKTOK_REFRESH_TOKEN,
        },
        timeout=30,
    )

    if resp.status_code == 200:
        data = resp.json()
        new_token = data.get("access_token")
        if new_token:
            _current_token = new_token
            env_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
            )
            try:
                set_key(env_path, "TIKTOK_ACCESS_TOKEN", new_token)
                new_refresh = data.get("refresh_token")
                if new_refresh:
                    set_key(env_path, "TIKTOK_REFRESH_TOKEN", new_refresh)
                print("  [TikTok] 토큰 갱신 완료 (.env 업데이트)")
            except Exception:
                print(f"  [TikTok] 토큰 갱신됨. .env에 수동으로 업데이트하세요:")
                print(f"    TIKTOK_ACCESS_TOKEN={new_token}")
            logger.info("TikTok 액세스 토큰 갱신 완료")
            return _current_token

    logger.warning(f"TikTok 토큰 갱신 실패: {resp.status_code} - {resp.text}")
    print("  [TikTok] 토큰 갱신 실패 — 기존 토큰 사용")
    return _current_token


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
)
def _api_request(method, url, **kwargs):
    """재시도 가능한 API 요청"""
    kwargs.setdefault("timeout", 60)
    resp = method(url, **kwargs)
    if resp.status_code >= 500:
        raise requests.ConnectionError(f"서버 오류: {resp.status_code}")
    return resp


def _get_user_info(token):
    """사용자 정보 (팔로워 수 등)를 조회합니다."""
    resp = _api_request(
        requests.get,
        f"{API_BASE}/user/info/",
        params={
            "fields": "follower_count,following_count,likes_count,video_count",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    if resp.status_code == 200:
        data = resp.json().get("data", {}).get("user", {})
        return {
            "follower_count": data.get("follower_count", 0),
            "video_count": data.get("video_count", 0),
        }

    logger.warning(f"TikTok 사용자 정보 조회 실패: {resp.status_code}")
    return {"follower_count": 0, "video_count": 0}


def _get_video_list(token):
    """영상 목록과 성과를 조회합니다 (커서 기반 페이지네이션)."""
    cutoff = datetime.now() - timedelta(days=POST_MAX_AGE_DAYS)
    all_videos = []
    cursor = 0
    has_more = True

    while has_more:
        resp = _api_request(
            requests.post,
            f"{API_BASE}/video/list/",
            params={
                "fields": "id,create_time,title,cover_image_url,share_url,"
                          "view_count,like_count,comment_count,share_count",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "max_count": 20,
                "cursor": cursor,
            },
        )

        if resp.status_code != 200:
            logger.error(f"TikTok 영상 목록 조회 실패: {resp.status_code} - {resp.text}")
            break

        data = resp.json().get("data", {})
        videos = data.get("videos", [])

        if not videos:
            break

        for video in videos:
            create_time = video.get("create_time", 0)
            video_dt = datetime.fromtimestamp(create_time)
            if video_dt < cutoff:
                return all_videos
            all_videos.append(video)

        has_more = data.get("has_more", False)
        cursor = data.get("cursor", 0)

    return all_videos


def fetch_tiktok_data():
    """TikTok 영상별 성과 데이터를 수집합니다.

    Returns:
        (List[Dict], Dict) - (영상별 데이터, 요약 데이터)
    """
    if not TIKTOK_CLIENT_KEY or not TIKTOK_CLIENT_SECRET:
        print("  [TikTok] 크레덴셜이 설정되지 않았습니다.")
        return [], {}

    if not _current_token and not TIKTOK_REFRESH_TOKEN:
        print("  [TikTok] 액세스 토큰이 설정되지 않았습니다.")
        return [], {}

    # 토큰 갱신
    token = _refresh_access_token()

    # 사용자 정보
    print("  [TikTok] 사용자 정보 조회 중...")
    user_info = _get_user_info(token)
    followers = user_info.get("follower_count", 0)

    # 영상 목록
    print("  [TikTok] 영상 목록 조회 중...")
    video_list = _get_video_list(token)
    print(f"  [TikTok] {len(video_list)}개 영상 발견 (팔로워: {followers:,})")

    if not video_list:
        return [], {}

    posts = []
    total_views = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_engagement = 0

    for i, video in enumerate(video_list):
        vid = str(video.get("id", ""))
        title = (video.get("title") or "")[:30]
        create_time = video.get("create_time", 0)
        pub_date = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d") if create_time else ""
        link = video.get("share_url", "")
        thumbnail = video.get("cover_image_url", "")

        views = video.get("view_count", 0)
        likes = video.get("like_count", 0)
        comments = video.get("comment_count", 0)
        shares = video.get("share_count", 0)

        # 참여율: (좋아요 + 댓글 + 공유) / 조회수 * 100
        engagement = round((likes + comments + shares) / views * 100, 2) if views > 0 else 0

        post = {
            "날짜": today,
            "게시물ID": vid,
            "캡션": title,
            "게시일": pub_date,
            "타입": "VIDEO",
            "링크": link,
            "썸네일": thumbnail,
            "조회수": views,
            "좋아요": likes,
            "댓글": comments,
            "공유": shares,
            "저장": "-",
            "팔로워유입": "-",
            "참여율(%)": engagement,
        }
        posts.append(post)

        total_views += views
        total_likes += likes
        total_comments += comments
        total_shares += shares
        total_engagement += engagement

        if (i + 1) % 10 == 0:
            print(f"  [TikTok] {i + 1}/{len(video_list)} 영상 처리 완료")

    # 요약
    avg_engagement = round(total_engagement / len(posts), 2) if posts else 0

    summary = {
        "날짜": today,
        "채널": "TikTok",
        "총게시물수": len(posts),
        "총조회수": total_views,
        "총좋아요": total_likes,
        "총댓글": total_comments,
        "총공유": total_shares,
        "평균참여율(%)": avg_engagement,
        "팔로워수": followers,
    }

    print(f"  [TikTok] 수집 완료: {len(posts)}개 영상, 팔로워 {followers:,}")
    return posts, summary
