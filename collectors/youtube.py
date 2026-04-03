"""YouTube 영상별 성과 수집 (Data API v3 + Analytics API)"""

import logging
from datetime import datetime, timedelta

import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN,
    YOUTUBE_CHANNEL_ID, POST_MAX_AGE_DAYS, today,
)

logger = logging.getLogger("sns_performance")

DATA_API_BASE = "https://www.googleapis.com/youtube/v3"
ANALYTICS_API_BASE = "https://youtubeanalytics.googleapis.com/v2"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def _get_access_token():
    """OAuth 리프레시 토큰으로 액세스 토큰을 발급받습니다."""
    creds = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds.token


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
        raise requests.ConnectionError(f"서버 오류: {resp.status_code} - {resp.text}")
    return resp


def _get_uploads_playlist(token):
    """채널의 업로드 재생목록 ID를 조회합니다.

    YOUTUBE_CHANNEL_ID가 설정되어 있으면 해당 채널을, 없으면 mine=true를 사용합니다.
    """
    if YOUTUBE_CHANNEL_ID:
        params = {"part": "contentDetails,statistics", "id": YOUTUBE_CHANNEL_ID}
    else:
        params = {"part": "contentDetails,statistics", "mine": "true"}

    resp = _api_request(
        requests.get,
        f"{DATA_API_BASE}/channels",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        raise Exception(f"채널 조회 실패: {resp.status_code} - {resp.text}")

    items = resp.json().get("items", [])
    if not items:
        raise Exception("채널을 찾을 수 없습니다.")

    channel = items[0]
    playlist_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    subscribers = int(channel["statistics"].get("subscriberCount", 0))
    return playlist_id, subscribers


def _get_video_list(token, playlist_id):
    """업로드 재생목록에서 영상 목록을 조회합니다 (POST_MAX_AGE_DAYS 이내)."""
    cutoff = datetime.now() - timedelta(days=POST_MAX_AGE_DAYS)
    video_ids = []
    page_token = None

    while True:
        params = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        resp = _api_request(
            requests.get,
            f"{DATA_API_BASE}/playlistItems",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            logger.error(f"영상 목록 조회 실패: {resp.status_code}")
            break

        data = resp.json()
        for item in data.get("items", []):
            snippet = item["snippet"]
            published = snippet.get("publishedAt", "")
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if pub_dt.replace(tzinfo=None) < cutoff:
                return video_ids

            video_ids.append({
                "id": snippet["resourceId"]["videoId"],
                "title": snippet.get("title", ""),
                "publishedAt": published[:10],
            })

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return video_ids


def _get_video_statistics(token, video_ids):
    """영상 통계를 일괄 조회합니다 (최대 50개씩)."""
    stats = {}

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        ids_str = ",".join(v["id"] for v in batch)

        resp = _api_request(
            requests.get,
            f"{DATA_API_BASE}/videos",
            params={
                "part": "statistics,snippet",
                "id": ids_str,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            logger.error(f"영상 통계 조회 실패: {resp.status_code}")
            continue

        for item in resp.json().get("items", []):
            vid = item["id"]
            s = item.get("statistics", {})
            stats[vid] = {
                "viewCount": int(s.get("viewCount", 0)),
                "likeCount": int(s.get("likeCount", 0)),
                "commentCount": int(s.get("commentCount", 0)),
                "favoriteCount": int(s.get("favoriteCount", 0)),
            }

    return stats


def _get_video_analytics(token, video_id, start_date):
    """YouTube Analytics API로 영상별 공유수, 구독자 증감을 조회합니다."""
    channel_id = YOUTUBE_CHANNEL_ID or "MINE"
    resp = _api_request(
        requests.get,
        f"{ANALYTICS_API_BASE}/reports",
        params={
            "ids": f"channel=={channel_id}",
            "filters": f"video=={video_id}",
            "startDate": start_date,
            "endDate": today,
            "metrics": "shares,subscribersGained",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    result = {"shares": 0, "subscribersGained": 0}

    if resp.status_code == 200:
        rows = resp.json().get("rows", [])
        for row in rows:
            result["shares"] += row[0] if len(row) > 0 else 0
            result["subscribersGained"] += row[1] if len(row) > 1 else 0
    else:
        logger.warning(f"Analytics 조회 실패 (video={video_id}): {resp.status_code}")

    return result


def fetch_youtube_data():
    """YouTube 영상별 성과 데이터를 수집합니다.

    Returns:
        (List[Dict], Dict) - (영상별 데이터, 요약 데이터)
    """
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET or not YOUTUBE_REFRESH_TOKEN:
        print("  [YouTube] 크레덴셜이 설정되지 않았습니다.")
        return [], {}

    print("  [YouTube] 인증 중...")
    token = _get_access_token()

    print("  [YouTube] 영상 목록 조회 중...")
    playlist_id, subscribers = _get_uploads_playlist(token)
    video_list = _get_video_list(token, playlist_id)
    print(f"  [YouTube] {len(video_list)}개 영상 발견 (구독자: {subscribers:,})")

    if not video_list:
        return [], {}

    # 통계 일괄 조회
    print("  [YouTube] 영상 통계 조회 중...")
    all_stats = _get_video_statistics(token, video_list)

    posts = []
    total_views = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_engagement = 0

    for i, video in enumerate(video_list):
        vid = video["id"]
        title = video["title"][:30]
        pub_date = video["publishedAt"]
        link = f"https://youtu.be/{vid}"
        thumbnail = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

        stat = all_stats.get(vid, {})
        views = stat.get("viewCount", 0)
        likes = stat.get("likeCount", 0)
        comments = stat.get("commentCount", 0)

        # Analytics API로 공유수, 구독자 증감 조회
        analytics = _get_video_analytics(token, vid, pub_date)
        shares = analytics.get("shares", 0)
        subs_gained = analytics.get("subscribersGained", 0)

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
            "팔로워유입": subs_gained,
            "참여율(%)": engagement,
        }
        posts.append(post)

        total_views += views
        total_likes += likes
        total_comments += comments
        total_shares += shares
        total_engagement += engagement

        if (i + 1) % 10 == 0:
            print(f"  [YouTube] {i + 1}/{len(video_list)} 영상 처리 완료")

    # 요약
    avg_engagement = round(total_engagement / len(posts), 2) if posts else 0

    summary = {
        "날짜": today,
        "채널": "YouTube",
        "총게시물수": len(posts),
        "총조회수": total_views,
        "총좋아요": total_likes,
        "총댓글": total_comments,
        "총공유": total_shares,
        "평균참여율(%)": avg_engagement,
        "팔로워수": subscribers,
    }

    print(f"  [YouTube] 수집 완료: {len(posts)}개 영상, 구독자 {subscribers:,}")
    return posts, summary
