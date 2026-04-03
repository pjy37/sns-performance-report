"""Instagram 게시물별 성과 수집 (Meta Graph API)"""

import logging
import re
from datetime import datetime, timedelta

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    META_PAGE_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID,
    META_API_VERSION, POST_MAX_AGE_DAYS, today,
)

logger = logging.getLogger("sns_performance")

BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"


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


def _get_media_list():
    """게시물 목록을 조회합니다 (POST_MAX_AGE_DAYS 이내)."""
    cutoff = datetime.now() - timedelta(days=POST_MAX_AGE_DAYS)
    all_media = []
    url = f"{BASE_URL}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    params = {
        "fields": "id,caption,timestamp,media_type,permalink,like_count,comments_count,thumbnail_url,media_url",
        "limit": 50,
        "access_token": META_PAGE_ACCESS_TOKEN,
    }

    while url:
        resp = _api_request(requests.get, url, params=params)
        if resp.status_code != 200:
            logger.error(f"게시물 목록 조회 실패: {resp.status_code} - {resp.text}")
            break

        data = resp.json()
        for item in data.get("data", []):
            # Meta API 타임스탬프: '2026-03-31T09:35:21+0000' → Python 3.9 호환 파싱
            ts = re.sub(r'\+(\d{4})$', r'+\1'[:3] + r':\1'[3:], item["timestamp"])
            ts = ts.replace("Z", "+00:00")
            # +0000 → +00:00 변환
            ts = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', ts)
            post_time = datetime.fromisoformat(ts)
            if post_time.replace(tzinfo=None) < cutoff:
                return all_media
            all_media.append(item)

        # 페이지네이션
        paging = data.get("paging", {})
        url = paging.get("next")
        params = {}  # next URL에 파라미터 포함됨

    return all_media


def _get_media_insights(media_id, media_type):
    """게시물별 인사이트를 조회합니다.

    미디어 타입별로 지원되는 메트릭이 다르므로 여러 조합을 시도합니다.
    instagram_manage_insights 권한이 없으면 빈 dict를 반환합니다.
    """
    # 미디어 타입별 지원 메트릭 (Meta Graph API v21.0+)
    # REELS(VIDEO): reach, saved, shares, total_interactions, plays
    # IMAGE/CAROUSEL: reach, saved, shares, total_interactions
    # impressions, follows는 최신 API에서 일부 타입 미지원
    metric_sets = [
        "reach,saved,shares",              # v21.0+ 안전한 조합
        "reach,saved,shares,impressions",  # 구형 API 호환
    ]

    insights = {}

    for metrics in metric_sets:
        resp = _api_request(
            requests.get,
            f"{BASE_URL}/{media_id}/insights",
            params={
                "metric": metrics,
                "access_token": META_PAGE_ACCESS_TOKEN,
            },
        )

        if resp.status_code == 200:
            for item in resp.json().get("data", []):
                name = item.get("name", "")
                value = item.get("values", [{}])[0].get("value", 0)
                insights[name] = value
            break  # 성공하면 중단
        else:
            error_data = resp.json().get("error", {})
            error_code = error_data.get("code", 0)
            error_msg = error_data.get("message", "")

            # 권한 없음 → 스킵
            if error_code == 190 or "permission" in error_msg.lower():
                break
            # 메트릭 미지원 → 다음 조합 시도
            elif error_code == 100 and "not support" in error_msg.lower():
                continue
            elif error_code == 100 and "no longer supported" in error_msg.lower():
                continue
            else:
                logger.warning(f"인사이트 조회 실패 (media_id={media_id}): {resp.status_code} - {error_msg}")
                break

    return insights


def _get_followers_count():
    """계정 팔로워 수를 조회합니다."""
    resp = _api_request(
        requests.get,
        f"{BASE_URL}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}",
        params={
            "fields": "followers_count",
            "access_token": META_PAGE_ACCESS_TOKEN,
        },
    )
    if resp.status_code == 200:
        return resp.json().get("followers_count", 0)
    return 0


def fetch_instagram_data():
    """Instagram 게시물별 성과 데이터를 수집합니다.

    Returns:
        (List[Dict], Dict) - (게시물별 데이터, 요약 데이터)
    """
    if not META_PAGE_ACCESS_TOKEN or not INSTAGRAM_BUSINESS_ACCOUNT_ID:
        print("  [Instagram] 크레덴셜이 설정되지 않았습니다.")
        return [], {}

    print("  [Instagram] 게시물 목록 조회 중...")
    media_list = _get_media_list()
    print(f"  [Instagram] {len(media_list)}개 게시물 발견")

    if not media_list:
        return [], {}

    posts = []
    total_views = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_engagement = 0

    for i, media in enumerate(media_list):
        media_id = media["id"]
        media_type = media.get("media_type", "")
        caption = (media.get("caption") or "")[:30]
        post_date = media["timestamp"][:10]
        permalink = media.get("permalink", "")
        thumbnail = media.get("thumbnail_url") or media.get("media_url", "")
        likes = media.get("like_count", 0)
        comments = media.get("comments_count", 0)

        # 인사이트 조회 (instagram_manage_insights 권한 필요)
        insights = _get_media_insights(media_id, media_type)
        # Meta API v21.0+에서 impressions/plays 미지원 → reach를 조회수로 사용
        reach = insights.get("reach", 0)
        views = insights.get("impressions", 0) or reach
        saved = insights.get("saved", 0)
        shares = insights.get("shares", 0)
        follows = insights.get("follows", 0)

        # 참여율 계산
        # 인사이트가 있으면: (좋아요 + 댓글 + 저장 + 공유) / 도달 * 100
        # 인사이트가 없으면: (좋아요 + 댓글) / 팔로워수 * 100 (나중에 계산)
        if reach > 0:
            engagement = round((likes + comments + saved + shares) / reach * 100, 2)
        else:
            engagement = 0  # 팔로워 수로 나중에 재계산

        post = {
            "날짜": today,
            "게시물ID": media_id,
            "캡션": caption,
            "게시일": post_date,
            "타입": media_type,
            "링크": permalink,
            "썸네일": thumbnail,
            "조회수": views,
            "좋아요": likes,
            "댓글": comments,
            "공유": shares,
            "저장": saved,
            "팔로워유입": follows,
            "참여율(%)": engagement,
        }
        posts.append(post)

        total_views += views
        total_likes += likes
        total_comments += comments
        total_shares += shares
        total_engagement += engagement

        if (i + 1) % 10 == 0:
            print(f"  [Instagram] {i + 1}/{len(media_list)} 게시물 처리 완료")

    # 팔로워 수 조회
    followers = _get_followers_count()

    # 인사이트가 없던 게시물의 참여율을 팔로워 기반으로 재계산
    if followers > 0:
        total_engagement = 0
        for post in posts:
            if post["참여율(%)"] == 0 and (post["좋아요"] > 0 or post["댓글"] > 0):
                post["참여율(%)"] = round(
                    (post["좋아요"] + post["댓글"]) / followers * 100, 2
                )
            total_engagement += post["참여율(%)"]

    # 요약
    avg_engagement = round(total_engagement / len(posts), 2) if posts else 0

    summary = {
        "날짜": today,
        "채널": "Instagram",
        "총게시물수": len(posts),
        "총조회수": total_views,
        "총좋아요": total_likes,
        "총댓글": total_comments,
        "총공유": total_shares,
        "평균참여율(%)": avg_engagement,
        "팔로워수": followers,
    }

    print(f"  [Instagram] 수집 완료: {len(posts)}개 게시물, 팔로워 {followers:,}")
    return posts, summary
