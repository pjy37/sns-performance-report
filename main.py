"""
SNS 성과 일일 리포트 자동화
============================
Instagram, YouTube, TikTok의 개별 게시물 성과를 수집하여
구글시트에 기록하고, 전일 대비 분석 후
슬랙 리포트 + HTML 보고서를 생성합니다.

사용법:
  python main.py

스케줄링 (매일 오전 9시 자동 실행):
  crontab -e
  0 9 * * * cd "/Users/gomak/Desktop/자동화/[자동화]SNS성과 리포트" && /usr/bin/python3 main.py >> cron.log 2>&1
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import today, yesterday
from collectors.instagram import fetch_instagram_data
from collectors.youtube import fetch_youtube_data
from collectors.tiktok import fetch_tiktok_data
from sheets import (
    write_post_data, write_summary, write_cross_comparison,
    get_previous_data, get_recent_data,
    update_content_db, update_weekly_status, update_monthly_dashboard,
    get_weekly_status_data, get_monthly_dashboard_data,
)
from analyzer import generate_analysis
from slack_sender import send_slack_report, send_error_notification
from report_generator import generate_html_report
from grader import apply_grades, detect_anomalies, calculate_channel_grade_stats
from ai_insights import generate_daily_insight, generate_content_recommendations


def main():
    print(f"{'=' * 60}")
    print(f"  SNS 성과 일일 리포트 - {today}")
    print(f"  실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")

    # ── 1단계: 게시물별 성과 수집 ──
    print("\n[1/5] 게시물별 성과 수집 중...")

    channel_posts = {}  # {"instagram": [...], "youtube": [...], "tiktok": [...]}
    channel_summaries = []
    errors = []

    # Instagram
    try:
        ig_posts, ig_summary = fetch_instagram_data()
        if ig_posts:
            channel_posts["instagram"] = ig_posts
        if ig_summary:
            channel_summaries.append(ig_summary)
    except Exception as e:
        msg = f"Instagram 수집 실패: {e}"
        print(f"  [Instagram] {msg}")
        errors.append(msg)

    # YouTube
    try:
        yt_posts, yt_summary = fetch_youtube_data()
        if yt_posts:
            channel_posts["youtube"] = yt_posts
        if yt_summary:
            channel_summaries.append(yt_summary)
    except Exception as e:
        msg = f"YouTube 수집 실패: {e}"
        print(f"  [YouTube] {msg}")
        errors.append(msg)

    # TikTok
    try:
        tt_posts, tt_summary = fetch_tiktok_data()
        if tt_posts:
            channel_posts["tiktok"] = tt_posts
        if tt_summary:
            channel_summaries.append(tt_summary)
    except Exception as e:
        msg = f"TikTok 수집 실패: {e}"
        print(f"  [TikTok] {msg}")
        errors.append(msg)

    total_posts = sum(len(posts) for posts in channel_posts.values())
    if total_posts == 0:
        print("\n  수집된 게시물이 없습니다. 종료합니다.")
        if errors:
            send_error_notification("\n".join(errors))
        return

    print(f"\n  총 {total_posts}개 게시물 수집 완료 ({len(channel_posts)}개 채널)")

    # ── 1.5단계: 콘텐츠 등급 산정 ──
    print("\n  콘텐츠 등급 산정 중...")
    grade_stats_by_channel = {}
    for channel_key, posts in channel_posts.items():
        apply_grades(posts)
        grade_stats = calculate_channel_grade_stats(posts)
        grade_stats_by_channel[channel_key] = grade_stats
        print(f"    [{channel_key}] S:{grade_stats['S']}개 A:{grade_stats['A']}개 B:{grade_stats['B']}개 C:{grade_stats['C']}개 (S+A비율 {grade_stats['SA비율']}%)")

    # 이상치 감지
    anomalies = detect_anomalies(channel_posts)
    if anomalies:
        print(f"\n  🚨 이상치 감지: {len(anomalies)}개 게시물이 평균 대비 {anomalies[0]['평균대비']}배 이상")

    # ── 2단계: 구글시트 기록 ──
    print("\n[2/6] 구글시트에 데이터 기록 중...")

    # 전일 요약 데이터 먼저 가져오기 (일간 증감 계산용)
    prev_summaries = []
    try:
        prev_summaries = get_previous_data("summary", yesterday)
        for s in prev_summaries:
            for key in ["총조회수", "총좋아요", "총댓글", "총공유", "평균참여율(%)", "팔로워수"]:
                if key in s:
                    try:
                        s[key] = float(s[key])
                    except (ValueError, TypeError):
                        s[key] = 0
    except Exception as e:
        print(f"  전일 요약 데이터 조회 실패: {e}")

    # 전일 데이터와 비교하여 일간 증감 계산
    prev_map = {s.get("채널", ""): s for s in prev_summaries}
    for summary in channel_summaries:
        channel = summary.get("채널", "")
        prev = prev_map.get(channel, {})
        summary["일간조회수"] = int(summary.get("총조회수", 0) - prev.get("총조회수", 0))
        summary["일간좋아요"] = int(summary.get("총좋아요", 0) - prev.get("총좋아요", 0))
        summary["일간댓글"] = int(summary.get("총댓글", 0) - prev.get("총댓글", 0))
        summary["팔로워증감"] = int(summary.get("팔로워수", 0) - prev.get("팔로워수", 0))

    try:
        for channel_key, posts in channel_posts.items():
            write_post_data(channel_key, posts)
        write_summary(channel_summaries)

        # 사용자 정의 시트 (콘텐츠 DB / 주간 / 월간) 자동 업데이트
        update_content_db(channel_posts)
        update_weekly_status(channel_summaries, grade_stats_by_channel)
        update_monthly_dashboard(channel_summaries, grade_stats_by_channel)
    except Exception as e:
        msg = f"구글시트 기록 실패: {e}"
        print(f"  [Sheets] {msg}")
        errors.append(msg)

    # ── 3단계: 전일 대비 분석 ──
    print("\n[3/6] 전일 대비 성과 분석 중...")

    # 전일 게시물 데이터 (Top 성장 게시물 계산용)
    prev_posts = {}
    for channel_key in channel_posts.keys():
        try:
            prev = get_previous_data(channel_key, yesterday)
            if prev:
                prev_posts[channel_key] = prev
        except Exception as e:
            print(f"  전일 {channel_key} 데이터 조회 실패: {e}")

    analysis = generate_analysis(channel_summaries, prev_summaries, channel_posts, prev_posts)

    # 분석 결과 콘솔 출력
    for ch in analysis.get("채널별", []):
        print(f"\n  [{ch.get('채널', '')}]")
        print(f"    게시물: {ch.get('총게시물수', 0)}개")
        print(f"    조회수: {ch.get('총조회수', 0):,} ({ch.get('조회수_변화', '-')})")
        print(f"    참여율: {ch.get('평균참여율(%)', 0)}% ({ch.get('참여율_변화', '-')})")
        print(f"    팔로워: {ch.get('팔로워수', 0):,} ({ch.get('팔로워_변화', '-')})")

    top5 = analysis.get("성장_TOP5", [])
    if top5:
        print(f"\n  🔥 Top 5 성장 게시물:")
        for i, p in enumerate(top5, 1):
            print(f"    {i}. [{p['채널']}] \"{p['캡션']}\" +{p['조회수_증가']:,} 조회 (+{p['증가율(%)']}%)")

    # 크로스 비교 시트 기록
    cross_data = analysis.get("크로스비교", [])
    if cross_data:
        try:
            write_cross_comparison(cross_data)
        except Exception as e:
            msg = f"크로스비교 시트 기록 실패: {e}"
            print(f"  [Sheets] {msg}")
            errors.append(msg)

    # ── 4단계: AI 인사이트 생성 ──
    print("\n[4/6] AI 인사이트 생성 중...")

    ai_data = {"일일_인사이트": {}, "콘텐츠_추천": []}
    try:
        insight = generate_daily_insight(channel_summaries, channel_posts, analysis, anomalies)
        ai_data["일일_인사이트"] = insight
        if insight.get("요약"):
            print(f"  [AI] {insight['요약'][:100]}...")

        recommendations = generate_content_recommendations(channel_posts, analysis.get("성장_TOP5", []))
        ai_data["콘텐츠_추천"] = recommendations
        if recommendations:
            print(f"  [AI] 콘텐츠 추천 {len(recommendations)}개 생성")
    except Exception as e:
        print(f"  [AI] 인사이트 생성 실패: {e}")

    # ── 5단계: 슬랙 전송 ──
    print("\n[5/6] 슬랙에 리포트 전송 중...")

    try:
        send_slack_report(analysis)
    except Exception as e:
        msg = f"슬랙 전송 실패: {e}"
        print(f"  [Slack] {msg}")
        errors.append(msg)

    # ── 6단계: HTML 보고서 생성 ──
    print("\n[6/6] HTML 보고서 생성 중...")

    try:
        # 최근 7일 데이터 (차트용)
        recent_post_data = []
        for channel_key in channel_posts.keys():
            recent = get_recent_data(channel_key, days=7)
            recent_post_data.extend(recent)

        recent_summary_data = get_recent_data("summary", days=7)

        # 월별 데이터 (최근 90일)
        monthly_summary_data = get_recent_data("summary", days=90)

        # 주간/월간 사용자 시트 데이터
        weekly_status_data = get_weekly_status_data()
        monthly_dashboard_data = get_monthly_dashboard_data()

        generate_html_report(
            analysis, channel_summaries, channel_posts,
            recent_post_data, recent_summary_data,
            grade_stats=grade_stats_by_channel,
            anomalies=anomalies,
            ai_data=ai_data,
            monthly_data=monthly_summary_data,
            weekly_status=weekly_status_data,
            monthly_dashboard=monthly_dashboard_data,
        )
    except Exception as e:
        msg = f"HTML 보고서 생성 실패: {e}"
        print(f"  [Report] {msg}")
        errors.append(msg)

    # ── 완료 ──
    print(f"\n{'=' * 60}")
    if errors:
        print(f"  완료 (경고 {len(errors)}건)")
        for err in errors:
            print(f"    - {err}")
        send_error_notification("에러 목록:\n" + "\n".join(errors))
    else:
        print("  모든 단계 정상 완료!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
