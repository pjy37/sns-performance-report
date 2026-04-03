"""HTML 보고서 생성 - 탭 네비게이션 + plotly 차트"""

import os
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
COLORS = {"Instagram": "#E1306C", "YouTube": "#FF0000", "TikTok": "#000000"}
CHANNEL_ICONS = {"Instagram": "instagram", "YouTube": "youtube", "TikTok": "tiktok"}
CHANNEL_URLS = {
    "Instagram": "https://www.instagram.com/zn.co.kr_/",
    "YouTube": "https://www.youtube.com/@%EC%9C%A0%EC%95%84%EC%97%B0-v8w",
    "TikTok": "https://www.tiktok.com/@zn.co.kr_?is_from_webapp=1&sender_device=pc",
}


def _ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


def _safe_num(v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v.replace(",", ""))
        except (ValueError, TypeError):
            pass
    return 0


def _fmt(n):
    n = _safe_num(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return f"{n:,.0f}"


# ─────────────────────────────────────────
#  차트 생성 함수
# ─────────────────────────────────────────

def _chart_channel_overview(channel_summaries):
    """채널별 조회수 + 좋아요 비교 바차트"""
    if not channel_summaries:
        return ""
    channels = [s.get("채널", "") for s in channel_summaries]
    views = [_safe_num(s.get("총조회수", 0)) for s in channel_summaries]
    likes = [_safe_num(s.get("총좋아요", 0)) for s in channel_summaries]
    colors = [COLORS.get(ch, "#666") for ch in channels]

    fig = go.Figure()
    light_colors = [f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.5)" for c in colors]
    fig.add_trace(go.Bar(x=channels, y=views, name="조회수", marker_color=colors))
    fig.add_trace(go.Bar(x=channels, y=likes, name="좋아요", marker_color=light_colors))
    fig.update_layout(barmode="group", template="plotly_white", height=300, margin=dict(t=30, b=30))
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _chart_cross_comparison(cross_data):
    """크로스 플랫폼 비교"""
    if not cross_data:
        return ""
    labels = [c.get("캡션", "")[:15] or c.get("게시일", "") for c in cross_data[:10]]
    ig = [_safe_num(c.get("IG조회수", 0)) for c in cross_data[:10]]
    yt = [_safe_num(c.get("YT조회수", 0)) for c in cross_data[:10]]
    tt = [_safe_num(c.get("TT조회수", 0)) for c in cross_data[:10]]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=ig, name="Instagram", marker_color=COLORS["Instagram"]))
    fig.add_trace(go.Bar(x=labels, y=yt, name="YouTube", marker_color=COLORS["YouTube"]))
    fig.add_trace(go.Bar(x=labels, y=tt, name="TikTok", marker_color=COLORS["TikTok"]))
    fig.update_layout(barmode="group", template="plotly_white", height=350, margin=dict(t=30, b=60),
                      xaxis_tickangle=-30, yaxis_title="조회수")
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _chart_platform_posts(posts, color):
    """특정 플랫폼의 게시물별 조회수 바차트"""
    if not posts:
        return ""
    sorted_posts = sorted(posts, key=lambda p: _safe_num(p.get("조회수", 0)), reverse=True)[:10]
    labels = [p.get("캡션", "")[:20] or p.get("게시물ID", "")[:10] for p in sorted_posts]
    views = [_safe_num(p.get("조회수", 0)) for p in sorted_posts]
    labels.reverse()
    views.reverse()

    fig = go.Figure(go.Bar(y=labels, x=views, orientation="h", marker_color=color,
                           text=[_fmt(v) for v in views], textposition="auto"))
    fig.update_layout(template="plotly_white", height=max(250, len(labels) * 40 + 60),
                      margin=dict(t=10, b=30, l=180), xaxis_title="조회수")
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _chart_engagement_trend(summary_data):
    """채널별 참여율 추이"""
    if not summary_data:
        return ""
    df = pd.DataFrame(summary_data)
    df["평균참여율(%)"] = pd.to_numeric(df["평균참여율(%)"], errors="coerce").fillna(0)
    fig = go.Figure()
    for ch in df["채널"].unique():
        d = df[df["채널"] == ch].sort_values("날짜")
        fig.add_trace(go.Scatter(x=d["날짜"], y=d["평균참여율(%)"], mode="lines+markers",
                                 name=ch, line=dict(color=COLORS.get(ch, "#666"))))
    fig.update_layout(template="plotly_white", height=300, margin=dict(t=30, b=30),
                      yaxis_title="참여율 (%)")
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _get_7day_xaxis(base_date=None):
    """7일 범위의 x축 설정을 반환합니다."""
    from datetime import timedelta
    if base_date is None:
        base_date = datetime.now()
    elif isinstance(base_date, str):
        base_date = datetime.strptime(base_date, "%Y-%m-%d")

    end = base_date
    start = end - timedelta(days=6)

    # 7일간의 날짜 목록 (M.DD 형식)
    dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    labels = [(start + timedelta(days=i)).strftime("%-m.%d") for i in range(7)]

    return dates, labels, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _apply_7day_xaxis(fig, base_date=None):
    """차트에 7일 고정 x축을 적용합니다."""
    dates, labels, start, end = _get_7day_xaxis(base_date)
    fig.update_xaxes(
        type="category",
        categoryorder="array",
        categoryarray=dates,
        ticktext=labels,
        tickvals=dates,
    )


def _chart_daily_views_trend(summary_data):
    """채널별 일별 조회수 추이 (7일)"""
    if not summary_data:
        return ""
    df = pd.DataFrame(summary_data)
    df["총조회수"] = pd.to_numeric(df["총조회수"], errors="coerce").fillna(0)

    dates, labels, _, _ = _get_7day_xaxis()

    fig = go.Figure()
    for ch in df["채널"].unique():
        d = df[df["채널"] == ch].sort_values("날짜")
        # 7일 전체를 채우기 위해 reindex
        d_map = dict(zip(d["날짜"], d["총조회수"]))
        y_vals = [d_map.get(dt, None) for dt in dates]
        fig.add_trace(go.Scatter(x=labels, y=y_vals, mode="lines+markers",
                                 name=ch, line=dict(color=COLORS.get(ch, "#666"), width=2),
                                 connectgaps=True, hovertemplate="%{y:,.0f}<extra></extra>"))
    fig.update_layout(template="plotly_white", height=320, margin=dict(t=30, b=40),
                      yaxis_title="총 조회수", legend=dict(orientation="h", y=-0.18))
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _chart_daily_followers_trend(summary_data):
    """채널별 일별 팔로워 추이 (7일)"""
    if not summary_data:
        return ""
    df = pd.DataFrame(summary_data)
    df["팔로워수"] = pd.to_numeric(df["팔로워수"], errors="coerce").fillna(0)

    dates, labels, _, _ = _get_7day_xaxis()

    fig = go.Figure()
    for ch in df["채널"].unique():
        d = df[df["채널"] == ch].sort_values("날짜")
        d_map = dict(zip(d["날짜"], d["팔로워수"]))
        y_vals = [d_map.get(dt, None) for dt in dates]
        fig.add_trace(go.Scatter(x=labels, y=y_vals, mode="lines+markers",
                                 name=ch, line=dict(color=COLORS.get(ch, "#666"), width=2),
                                 connectgaps=True, hovertemplate="%{y:,.0f}<extra></extra>"))
    fig.update_layout(template="plotly_white", height=320, margin=dict(t=30, b=40),
                      yaxis_title="팔로워 수", legend=dict(orientation="h", y=-0.18))
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _chart_daily_engagement_trend(summary_data):
    """채널별 일별 참여율 추이 (7일)"""
    if not summary_data:
        return ""
    df = pd.DataFrame(summary_data)
    df["평균참여율(%)"] = pd.to_numeric(df["평균참여율(%)"], errors="coerce").fillna(0)

    dates, labels, _, _ = _get_7day_xaxis()

    fig = go.Figure()
    for ch in df["채널"].unique():
        d = df[df["채널"] == ch].sort_values("날짜")
        d_map = dict(zip(d["날짜"], d["평균참여율(%)"]))
        y_vals = [d_map.get(dt, None) for dt in dates]
        fig.add_trace(go.Scatter(x=labels, y=y_vals, mode="lines+markers",
                                 name=ch, line=dict(color=COLORS.get(ch, "#666"), width=2),
                                 connectgaps=True, hovertemplate="%{y:.1f}%<extra></extra>"))
    fig.update_layout(template="plotly_white", height=320, margin=dict(t=30, b=40),
                      yaxis_title="참여율 (%)", legend=dict(orientation="h", y=-0.18))
    return fig.to_html(full_html=False, include_plotlyjs=False)


def _build_daily_summary_table(summary_data):
    """7일간 일별 요약 테이블"""
    if not summary_data:
        return ""
    df = pd.DataFrame(summary_data)
    dates = sorted(df["날짜"].unique(), reverse=True)

    rows = ""
    for date in dates:
        # M.DD 형식으로 변환
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            short_date = dt.strftime("%-m.%d")
        except ValueError:
            short_date = date

        day_data = df[df["날짜"] == date]
        for _, row in day_data.iterrows():
            ch = row.get("채널", "")
            color = COLORS.get(ch, "#666")
            rows += f"""<tr>
                <td>{short_date}</td>
                <td style="color:{color};font-weight:600">{ch}</td>
                <td>{_fmt(row.get('총게시물수', 0))}</td>
                <td>{_fmt(row.get('총조회수', 0))}</td>
                <td>{_fmt(row.get('총좋아요', 0))}</td>
                <td>{_fmt(row.get('총댓글', 0))}</td>
                <td>{_safe_num(row.get('평균참여율(%)', 0)):.1f}%</td>
                <td>{_fmt(row.get('팔로워수', 0))}</td>
            </tr>"""

    return f"""
    <table>
        <thead><tr>
            <th style="text-align:left">날짜</th><th>채널</th><th>게시물</th><th>조회수</th>
            <th>좋아요</th><th>댓글</th><th>참여율</th><th>팔로워</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>"""


# ─────────────────────────────────────────
#  HTML 구성 요소
# ─────────────────────────────────────────

def _build_channel_card(name, summary, url):
    """채널 요약 카드"""
    followers = _fmt(summary.get("팔로워수", 0))
    views = _fmt(summary.get("총조회수", 0))
    likes = _fmt(summary.get("총좋아요", 0))
    posts = summary.get("총게시물수", 0)
    engagement = f"{_safe_num(summary.get('평균참여율(%)', 0)):.1f}%"
    color = COLORS.get(name, "#666")

    return f"""
    <div class="channel-card" style="border-top: 4px solid {color}">
        <div class="card-header">
            <h3>{name}</h3>
            <a href="{url}" target="_blank" class="card-link">채널 바로가기 &rarr;</a>
        </div>
        <div class="card-stats">
            <div class="stat"><span class="stat-value">{followers}</span><span class="stat-label">팔로워</span></div>
            <div class="stat"><span class="stat-value">{views}</span><span class="stat-label">총 조회수</span></div>
            <div class="stat"><span class="stat-value">{likes}</span><span class="stat-label">총 좋아요</span></div>
            <div class="stat"><span class="stat-value">{posts}</span><span class="stat-label">게시물</span></div>
            <div class="stat"><span class="stat-value">{engagement}</span><span class="stat-label">참여율</span></div>
        </div>
    </div>"""


def _build_post_cards(posts, platform):
    """게시물 카드 그리드 (정렬 버튼 포함)"""
    if not posts:
        return "<p class='empty'>데이터가 없습니다.</p>"

    show_save = platform == "instagram"
    grid_id = f"grid-{platform}"

    # 기본 정렬: 조회수 높은 순
    sorted_posts = sorted(posts, key=lambda x: _safe_num(x.get("조회수", 0)), reverse=True)

    cards = ""
    for i, p in enumerate(sorted_posts):
        link = p.get("링크", "")
        caption = p.get("캡션", "")[:30]
        pub = p.get("게시일", "")
        thumb = p.get("썸네일", "")
        views_raw = _safe_num(p.get("조회수", 0))
        views = _fmt(views_raw)
        likes = _fmt(p.get("좋아요", 0))
        comments = _fmt(p.get("댓글", 0))
        shares = _fmt(p.get("공유", 0))
        saved = p.get("저장", "-")
        if saved != "-":
            saved = _fmt(saved)
        engagement = f"{_safe_num(p.get('참여율(%)', 0)):.1f}%"

        thumb_html = f'<img src="{thumb}" alt="" loading="lazy">' if thumb else '<div class="no-thumb">No Image</div>'
        save_row = f'<div class="post-metric"><span class="pm-label">저장</span><span class="pm-value">{saved}</span></div>' if show_save else ""

        cards += f"""
        <a href="{link}" target="_blank" class="post-card" data-views="{int(views_raw)}" data-date="{pub}">
            <div class="post-thumb">
                <span class="post-rank"></span>
                {thumb_html}
            </div>
            <div class="post-info">
                <div class="post-caption">{caption}</div>
                <div class="post-date">{pub}</div>
                <div class="post-metrics">
                    <div class="post-metric"><span class="pm-label">조회수</span><span class="pm-value">{views}</span></div>
                    <div class="post-metric"><span class="pm-label">좋아요</span><span class="pm-value">{likes}</span></div>
                    <div class="post-metric"><span class="pm-label">댓글</span><span class="pm-value">{comments}</span></div>
                    <div class="post-metric"><span class="pm-label">공유</span><span class="pm-value">{shares}</span></div>
                    {save_row}
                    <div class="post-metric"><span class="pm-label">참여율</span><span class="pm-value">{engagement}</span></div>
                </div>
            </div>
        </a>"""

    sort_buttons = f"""
    <div class="sort-bar">
        <span class="sort-label">정렬:</span>
        <button class="sort-btn active" onclick="sortCards('{grid_id}','views',this)">조회수 높은 순</button>
        <button class="sort-btn" onclick="sortCards('{grid_id}','date',this)">최근 업로드 순</button>
    </div>"""

    return f'{sort_buttons}<div class="post-grid" id="{grid_id}">{cards}</div>'


def _build_cross_table(cross_data):
    """크로스비교 테이블"""
    if not cross_data:
        return "<p class='empty'>동일 게시일에 2개 이상 채널에 올린 콘텐츠가 없습니다.</p>"

    rows = ""
    for c in cross_data:
        caption = c.get("캡션", "")[:20]
        pub = c.get("게시일", "")
        best = c.get("최고채널", "-")
        best_color = COLORS.get(best, "#666")

        rows += f"""<tr>
            <td style="text-align:left">{caption}</td>
            <td>{pub}</td>
            <td>{_fmt(c.get('IG조회수', 0))}</td>
            <td>{_fmt(c.get('IG좋아요', 0))}</td>
            <td>{_fmt(c.get('YT조회수', 0))}</td>
            <td>{_fmt(c.get('YT좋아요', 0))}</td>
            <td>{_fmt(c.get('TT조회수', 0))}</td>
            <td>{_fmt(c.get('TT좋아요', 0))}</td>
            <td>{_fmt(c.get('총조회수', 0))}</td>
            <td style="color:{best_color};font-weight:700">{best}</td>
        </tr>"""

    return f"""
    <table class="cross-table">
        <thead><tr>
            <th style="text-align:left" rowspan="2">콘텐츠</th><th rowspan="2">게시일</th>
            <th colspan="2" style="color:{COLORS['Instagram']}">Instagram</th>
            <th colspan="2" style="color:{COLORS['YouTube']}">YouTube</th>
            <th colspan="2">TikTok</th>
            <th rowspan="2">총조회</th><th rowspan="2">최고채널</th>
        </tr><tr>
            <th>조회</th><th>좋아요</th><th>조회</th><th>좋아요</th><th>조회</th><th>좋아요</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>"""


# ─────────────────────────────────────────
#  메인 생성 함수
# ─────────────────────────────────────────

def generate_html_report(analysis, channel_summaries, channel_posts, recent_post_data, recent_summary_data):
    """HTML 보고서를 생성합니다."""
    _ensure_reports_dir()

    date = analysis.get("날짜", datetime.now().strftime("%Y-%m-%d"))
    cross_data = analysis.get("크로스비교", [])
    top_growing = analysis.get("성장_TOP5", [])

    # 요약 맵 생성
    summary_map = {s.get("채널", ""): s for s in channel_summaries}

    # 차트
    chart_overview = _chart_channel_overview(channel_summaries)
    chart_cross = _chart_cross_comparison(cross_data)

    # 주간 추이용 JSON 데이터 (JavaScript에서 렌더링)
    import json
    summary_json = json.dumps(recent_summary_data, ensure_ascii=False)

    ig_chart = _chart_platform_posts(channel_posts.get("instagram", []), COLORS["Instagram"])
    yt_chart = _chart_platform_posts(channel_posts.get("youtube", []), COLORS["YouTube"])
    tt_chart = _chart_platform_posts(channel_posts.get("tiktok", []), COLORS["TikTok"])

    # 채널 카드
    cards = ""
    for ch_name in ["Instagram", "YouTube", "TikTok"]:
        s = summary_map.get(ch_name, {})
        if s:
            cards += _build_channel_card(ch_name, s, CHANNEL_URLS.get(ch_name, "#"))

    # Top 성장 게시물
    top_html = ""
    if top_growing:
        for i, p in enumerate(top_growing, 1):
            ch = p.get("채널", "")
            color = COLORS.get({"IG": "Instagram", "YT": "YouTube", "TT": "TikTok"}.get(ch, ""), "#666")
            top_html += f"""
            <div class="top-item">
                <span class="top-rank">{i}</span>
                <span class="top-channel" style="color:{color}">[{ch}]</span>
                <span class="top-caption">"{p.get('캡션', '')}"</span>
                <span class="top-growth">+{_fmt(p.get('조회수_증가', 0))} 조회 (+{p.get('증가율(%)', 0)}%)</span>
            </div>"""

    # 개별 채널 카드 (각 탭용)
    ig_card = _build_channel_card("Instagram", summary_map.get("Instagram", {}), CHANNEL_URLS["Instagram"]) if "Instagram" in summary_map else "<p class='empty'>Instagram 데이터가 없습니다.</p>"
    yt_card = _build_channel_card("YouTube", summary_map.get("YouTube", {}), CHANNEL_URLS["YouTube"]) if "YouTube" in summary_map else "<p class='empty'>YouTube 데이터가 없습니다.</p>"
    tt_card = _build_channel_card("TikTok", summary_map.get("TikTok", {}), CHANNEL_URLS["TikTok"]) if "TikTok" in summary_map else "<p class='empty'>TikTok 데이터가 없습니다. 크레덴셜을 설정해주세요.</p>"

    # 게시물 카드
    ig_table = _build_post_cards(channel_posts.get("instagram", []), "instagram")
    yt_table = _build_post_cards(channel_posts.get("youtube", []), "youtube")
    tt_table = _build_post_cards(channel_posts.get("tiktok", []), "tiktok")
    cross_table = _build_cross_table(cross_data)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SNS 성과 보고서 - {date}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',sans-serif; background:#f0f2f5; color:#1a1a2e; font-size:14px; }}

/* 헤더 */
.header {{ background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:#fff; padding:32px 24px; text-align:center; }}
.header h1 {{ font-size:26px; font-weight:700; }}
.header .subtitle {{ opacity:0.85; margin-top:6px; font-size:15px; }}
.header .links {{ margin-top:14px; display:flex; justify-content:center; gap:16px; flex-wrap:wrap; }}
.header .links a {{ color:#fff; text-decoration:none; background:rgba(255,255,255,0.18); padding:6px 16px; border-radius:20px; font-size:13px; transition:background 0.2s; }}
.header .links a:hover {{ background:rgba(255,255,255,0.35); }}

/* 탭 네비게이션 */
.tab-nav {{ display:flex; background:#fff; border-bottom:2px solid #e8e8e8; padding:0 24px; position:sticky; top:0; z-index:100; box-shadow:0 2px 4px rgba(0,0,0,0.04); overflow-x:auto; }}
.tab-btn {{ padding:14px 24px; cursor:pointer; border:none; background:none; font-size:14px; font-weight:600; color:#888; border-bottom:3px solid transparent; transition:all 0.2s; white-space:nowrap; }}
.tab-btn:hover {{ color:#333; }}
.tab-btn.active {{ color:#667eea; border-bottom-color:#667eea; }}

/* 탭 콘텐츠 */
.tab-content {{ display:none; max-width:1200px; margin:0 auto; padding:24px; }}
.tab-content.active {{ display:block; }}

/* 섹션 */
.section {{ background:#fff; border-radius:12px; padding:24px; margin-bottom:20px; box-shadow:0 1px 4px rgba(0,0,0,0.06); }}
.section h2 {{ font-size:18px; margin-bottom:16px; padding-bottom:10px; border-bottom:2px solid #f0f0f0; color:#333; }}
.section h3 {{ font-size:15px; color:#555; margin:16px 0 10px; }}

/* 채널 카드 */
.channel-cards {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:16px; margin-bottom:20px; }}
.channel-card {{ background:#fff; border-radius:12px; padding:20px; box-shadow:0 1px 4px rgba(0,0,0,0.06); }}
.card-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; }}
.card-header h3 {{ font-size:17px; margin:0; }}
.card-link {{ font-size:12px; color:#667eea; text-decoration:none; }}
.card-link:hover {{ text-decoration:underline; }}
.card-stats {{ display:flex; gap:12px; flex-wrap:wrap; }}
.stat {{ text-align:center; flex:1; min-width:60px; }}
.stat-value {{ display:block; font-size:20px; font-weight:700; color:#1a1a2e; }}
.stat-label {{ display:block; font-size:11px; color:#999; margin-top:2px; }}

/* Top 성장 */
.top-item {{ display:flex; align-items:center; gap:10px; padding:10px 0; border-bottom:1px solid #f5f5f5; }}
.top-rank {{ background:#667eea; color:#fff; width:24px; height:24px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; flex-shrink:0; }}
.top-channel {{ font-weight:700; font-size:13px; flex-shrink:0; }}
.top-caption {{ color:#555; flex:1; font-size:13px; }}
.top-growth {{ color:#27ae60; font-weight:600; font-size:13px; flex-shrink:0; }}

/* 테이블 */
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#f8f9fb; font-weight:600; color:#555; padding:10px 12px; text-align:right; border-bottom:2px solid #eee; }}
td {{ padding:9px 12px; text-align:right; border-bottom:1px solid #f0f0f0; }}
th:first-child, td:first-child {{ text-align:left; }}
tr:hover td {{ background:#fafbff; }}
td a {{ color:#667eea; text-decoration:none; }}
td a:hover {{ text-decoration:underline; }}
.cross-table th {{ font-size:12px; padding:8px 10px; }}

/* 게시물 카드 그리드 */
.post-grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(260px, 1fr)); gap:16px; }}
.post-card {{ display:block; background:#fff; border:1px solid #eee; border-radius:10px; overflow:hidden; text-decoration:none; color:inherit; transition:transform 0.15s, box-shadow 0.15s; }}
.post-card:hover {{ transform:translateY(-3px); box-shadow:0 6px 16px rgba(0,0,0,0.1); }}
.post-thumb {{ position:relative; width:100%; padding-top:100%; background:#f0f0f0; overflow:hidden; }}
.post-thumb img {{ position:absolute; top:0; left:0; width:100%; height:100%; object-fit:cover; }}
.post-thumb .no-thumb {{ position:absolute; top:0; left:0; width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:#ccc; font-size:13px; }}
.post-rank {{ position:absolute; top:8px; left:8px; background:rgba(0,0,0,0.65); color:#fff; padding:3px 8px; border-radius:6px; font-size:12px; font-weight:700; z-index:2; }}
.post-info {{ padding:14px; }}
.post-caption {{ font-size:13px; font-weight:600; color:#222; line-height:1.4; margin-bottom:4px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }}
.post-date {{ font-size:11px; color:#aaa; margin-bottom:10px; }}
.post-metrics {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; }}
.post-metric {{ text-align:center; }}
.pm-label {{ display:block; font-size:10px; color:#999; }}
.pm-value {{ display:block; font-size:14px; font-weight:700; color:#333; }}

/* 주간 네비게이션 */
.week-btn {{ background:none; border:1px solid #ddd; padding:6px 16px; border-radius:6px; cursor:pointer; font-size:13px; color:#667eea; font-weight:600; transition:all 0.15s; }}
.week-btn:hover {{ background:#667eea; color:#fff; border-color:#667eea; }}
.week-btn:disabled {{ opacity:0.3; cursor:not-allowed; }}
.week-btn:disabled:hover {{ background:none; color:#667eea; border-color:#ddd; }}

/* 정렬 바 */
.sort-bar {{ display:flex; align-items:center; gap:8px; margin-bottom:14px; }}
.sort-label {{ font-size:12px; color:#999; }}
.sort-btn {{ padding:5px 14px; border:1px solid #ddd; border-radius:16px; background:#fff; font-size:12px; color:#666; cursor:pointer; transition:all 0.15s; }}
.sort-btn:hover {{ border-color:#667eea; color:#667eea; }}
.sort-btn.active {{ background:#667eea; color:#fff; border-color:#667eea; }}

.empty {{ color:#aaa; text-align:center; padding:40px; }}

/* 플랫폼 헤더 */
.platform-header {{ display:flex; align-items:center; gap:12px; margin-bottom:16px; }}
.platform-header .dot {{ width:12px; height:12px; border-radius:50%; }}
.platform-header h2 {{ border:none; padding:0; margin:0; }}
.platform-header a {{ font-size:12px; color:#667eea; text-decoration:none; margin-left:auto; }}

/* 푸터 */
.footer {{ text-align:center; padding:24px; color:#bbb; font-size:12px; }}
</style>
</head>
<body>

<!-- 헤더 -->
<div class="header">
    <h1>유아연 SNS 성과 보고서</h1>
    <div class="subtitle">{date} 기준 | 자동 생성 리포트</div>
    <div class="links">
        <a href="{CHANNEL_URLS['Instagram']}" target="_blank">Instagram</a>
        <a href="{CHANNEL_URLS['YouTube']}" target="_blank">YouTube</a>
        <a href="{CHANNEL_URLS['TikTok']}" target="_blank">TikTok</a>
        <a href="https://docs.google.com/spreadsheets/d/1A3InkFr2YXJWy6_B0FKWsglMcrlSrC4CUSdi4xet788" target="_blank">Google Sheets</a>
    </div>
</div>

<!-- 탭 네비게이션 -->
<div class="tab-nav">
    <button class="tab-btn active" onclick="openTab(event,'tab-overview')">통합 보고서</button>
    <button class="tab-btn" onclick="openTab(event,'tab-instagram')" style="color:{COLORS['Instagram']}">Instagram</button>
    <button class="tab-btn" onclick="openTab(event,'tab-youtube')" style="color:{COLORS['YouTube']}">YouTube</button>
    <button class="tab-btn" onclick="openTab(event,'tab-tiktok')">TikTok</button>
    <button class="tab-btn" onclick="openTab(event,'tab-cross')">크로스 비교</button>
</div>

<!-- ═══════ 통합 보고서 ═══════ -->
<div id="tab-overview" class="tab-content active">
    <div class="section">
        <h2>오늘의 채널 현황</h2>
        <div class="channel-cards">{cards}</div>
    </div>

    <div class="section">
        <h2>채널별 성과 비교 (오늘)</h2>
        {chart_overview}
    </div>

    <div class="section">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid #f0f0f0">
            <button class="week-btn" onclick="changeWeek(-1)">&larr; 이전 주</button>
            <h2 id="week-title" style="border:none;padding:0;margin:0">주간 추이</h2>
            <button class="week-btn" id="week-next-btn" onclick="changeWeek(1)">다음 주 &rarr;</button>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <div><h3 style="font-size:14px;color:#555;margin-bottom:8px">일간 조회수 증가</h3><div id="chart-views"></div></div>
            <div><h3 style="font-size:14px;color:#555;margin-bottom:8px">팔로워 증감</h3><div id="chart-followers"></div></div>
        </div>
        <div style="margin-top:12px">
            <h3 style="font-size:14px;color:#555;margin-bottom:8px">참여율</h3>
            <div id="chart-engagement"></div>
        </div>
    </div>

    <div class="section">
        <h2>일별 상세 데이터</h2>
        <div id="weekly-table"></div>
    </div>

    {"<div class='section'><h2>Top 성장 게시물</h2><p style='color:#888;font-size:12px;margin-bottom:12px;'>전일 대비 조회수 증가량 기준</p>" + top_html + "</div>" if top_html else ""}
</div>

<!-- ═══════ Instagram ═══════ -->
<div id="tab-instagram" class="tab-content">
    <div class="section">
        <div class="platform-header">
            <div class="dot" style="background:{COLORS['Instagram']}"></div>
            <h2>Instagram</h2>
            <a href="{CHANNEL_URLS['Instagram']}" target="_blank">@zn.co.kr_ &rarr;</a>
        </div>
        {ig_card}
    </div>
    {"<div class='section'><h3>게시물별 조회수</h3>" + ig_chart + "</div>" if ig_chart else ""}
    <div class="section">
        <h3>콘텐츠 DB</h3>
        {ig_table}
    </div>
</div>

<!-- ═══════ YouTube ═══════ -->
<div id="tab-youtube" class="tab-content">
    <div class="section">
        <div class="platform-header">
            <div class="dot" style="background:{COLORS['YouTube']}"></div>
            <h2>YouTube</h2>
            <a href="{CHANNEL_URLS['YouTube']}" target="_blank">@유아연 &rarr;</a>
        </div>
        {yt_card}
    </div>
    {"<div class='section'><h3>영상별 조회수</h3>" + yt_chart + "</div>" if yt_chart else ""}
    <div class="section">
        <h3>콘텐츠 DB</h3>
        {yt_table}
    </div>
</div>

<!-- ═══════ TikTok ═══════ -->
<div id="tab-tiktok" class="tab-content">
    <div class="section">
        <div class="platform-header">
            <div class="dot" style="background:{COLORS['TikTok']}"></div>
            <h2>TikTok</h2>
            <a href="{CHANNEL_URLS['TikTok']}" target="_blank">@zn.co.kr_ &rarr;</a>
        </div>
        {tt_card}
    </div>
    {"<div class='section'><h3>영상별 조회수</h3>" + tt_chart + "</div>" if tt_chart else ""}
    <div class="section">
        <h3>콘텐츠 DB</h3>
        {tt_table}
    </div>
</div>

<!-- ═══════ 크로스 비교 ═══════ -->
<div id="tab-cross" class="tab-content">
    <div class="section">
        <h2>크로스 플랫폼 비교</h2>
        <p style="color:#888;font-size:13px;margin-bottom:16px;">같은 날 2개 이상 채널에 올린 콘텐츠의 채널별 성과를 비교합니다.</p>
        {chart_cross}
    </div>
    <div class="section">
        <h3>상세 비교표</h3>
        {cross_table}
    </div>
</div>

<!-- 푸터 -->
<div class="footer">
    유아연 SNS 성과 자동화 리포트 | 생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
</div>

<script>
// 탭 전환
function openTab(evt, tabId) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    evt.currentTarget.classList.add('active');
    setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
}}

// ── 카드 정렬 ──
function sortCards(gridId, sortBy, btn) {{
    const grid = document.getElementById(gridId);
    const cards = Array.from(grid.querySelectorAll('.post-card'));

    // 버튼 활성화
    btn.parentElement.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    cards.sort((a, b) => {{
        if (sortBy === 'views') {{
            return parseInt(b.dataset.views || 0) - parseInt(a.dataset.views || 0);
        }} else {{
            return (b.dataset.date || '').localeCompare(a.dataset.date || '');
        }}
    }});

    cards.forEach((card, i) => {{
        card.querySelector('.post-rank').textContent = '#' + (i + 1);
        grid.appendChild(card);
    }});
}}

// 초기 랭크 번호 설정
document.addEventListener('DOMContentLoaded', () => {{
    document.querySelectorAll('.post-grid').forEach(grid => {{
        grid.querySelectorAll('.post-rank').forEach((rank, i) => {{
            rank.textContent = '#' + (i + 1);
        }});
    }});
}});

// ── 주간 네비게이션 ──
const SUMMARY_DATA = {summary_json};
const CHANNEL_COLORS = {{"Instagram":"#E1306C","YouTube":"#FF0000","TikTok":"#000000"}};
const TODAY = "{date}";
let weekOffset = 0;

function getMonday(d) {{
    const dt = new Date(d);
    const day = dt.getDay();
    const diff = dt.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(dt.setDate(diff));
}}

function addDays(d, n) {{
    const dt = new Date(d);
    dt.setDate(dt.getDate() + n);
    return dt;
}}

function fmtDate(d) {{
    return d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}}

function fmtShort(d) {{
    return (d.getMonth()+1) + '.' + String(d.getDate()).padStart(2,'0');
}}

function changeWeek(dir) {{
    weekOffset += dir;
    const todayMon = getMonday(new Date(TODAY));
    const targetMon = addDays(todayMon, weekOffset * 7);
    const targetSun = addDays(targetMon, 6);

    // 미래 주 차단
    if (targetMon > getMonday(new Date(TODAY))) {{
        weekOffset -= dir;
        return;
    }}
    document.getElementById('week-next-btn').disabled = (weekOffset >= 0);

    renderWeek(targetMon, targetSun);
}}

function renderWeek(mon, sun) {{
    const days = [];
    const labels = [];
    for (let i = 0; i < 7; i++) {{
        const d = addDays(mon, i);
        days.push(fmtDate(d));
        labels.push(fmtShort(d));
    }}

    // 제목
    document.getElementById('week-title').innerHTML =
        '주간 추이 <span style="font-size:14px;color:#888;font-weight:400">(' + fmtShort(mon) + ' ~ ' + fmtShort(sun) + ')</span>';

    // 이 주의 데이터 필터
    const weekData = SUMMARY_DATA.filter(r => r['날짜'] >= days[0] && r['날짜'] <= days[6]);
    const channels = [...new Set(weekData.map(r => r['채널']))];

    // 차트 그리기 함수
    function plotChart(divId, field, yTitle, fmt) {{
        const traces = channels.map(ch => {{
            const chData = {{}};
            weekData.filter(r => r['채널'] === ch).forEach(r => {{ chData[r['날짜']] = parseFloat(r[field]) || 0; }});
            return {{
                x: labels,
                y: days.map(d => chData[d] !== undefined ? chData[d] : null),
                mode: 'lines+markers',
                name: ch,
                connectgaps: true,
                line: {{ color: CHANNEL_COLORS[ch] || '#666', width: 2 }},
                hovertemplate: fmt
            }};
        }});
        Plotly.react(divId, traces.length ? traces : [{{x:labels,y:labels.map(()=>null),mode:'lines'}}], {{
            template: 'plotly_white', height: 280,
            margin: {{ t: 20, b: 40, l: 50, r: 20 }},
            yaxis: {{ title: yTitle }},
            legend: {{ orientation: 'h', y: -0.2 }},
            xaxis: {{ type: 'category' }}
        }}, {{ responsive: true }});
    }}

    plotChart('chart-views', '일간조회수', '일간 조회수', '%{{y:,.0f}}<extra></extra>');
    plotChart('chart-followers', '팔로워증감', '팔로워 증감', '%{{y:,.0f}}<extra></extra>');
    plotChart('chart-engagement', '평균참여율(%)', '참여율 (%)', '%{{y:.1f}}%<extra></extra>');

    // 테이블
    let tbl = '<table><thead><tr><th style="text-align:left">날짜</th><th>채널</th><th>일간조회</th><th>일간좋아요</th><th>일간댓글</th><th>참여율</th><th>팔로워증감</th><th>팔로워</th></tr></thead><tbody>';
    days.slice().reverse().forEach(d => {{
        const dayRows = weekData.filter(r => r['날짜'] === d);
        const short = fmtShort(new Date(d));
        dayRows.forEach(r => {{
            const color = CHANNEL_COLORS[r['채널']] || '#666';
            const dv = Number(r['일간조회수']||0);
            const dl = Number(r['일간좋아요']||0);
            const dc = Number(r['일간댓글']||0);
            const fg = Number(r['팔로워증감']||0);
            tbl += '<tr><td>' + short + '</td><td style="color:' + color + ';font-weight:600">' + r['채널'] + '</td>'
                + '<td>' + (dv >= 0 ? '+' : '') + dv.toLocaleString() + '</td>'
                + '<td>' + (dl >= 0 ? '+' : '') + dl.toLocaleString() + '</td>'
                + '<td>' + (dc >= 0 ? '+' : '') + dc.toLocaleString() + '</td>'
                + '<td>' + Number(r['평균참여율(%)']||0).toFixed(1) + '%</td>'
                + '<td style="color:' + (fg >= 0 ? '#27ae60' : '#e74c3c') + '">' + (fg >= 0 ? '+' : '') + fg.toLocaleString() + '</td>'
                + '<td>' + Number(r['팔로워수']||0).toLocaleString() + '</td></tr>';
        }});
    }});
    tbl += '</tbody></table>';
    if (!weekData.length) tbl = '<p class="empty">이 주간에는 데이터가 없습니다.</p>';
    document.getElementById('weekly-table').innerHTML = tbl;
}}

// 초기 렌더링
document.addEventListener('DOMContentLoaded', () => {{
    const todayMon = getMonday(new Date(TODAY));
    const todaySun = addDays(todayMon, 6);
    document.getElementById('week-next-btn').disabled = true;
    renderWeek(todayMon, todaySun);
}});
</script>
</body>
</html>"""

    filepath = os.path.join(REPORTS_DIR, f"{date}.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  [Report] HTML 보고서 생성: {filepath}")
    return filepath
