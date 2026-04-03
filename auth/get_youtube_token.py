"""
YouTube OAuth 2.0 리프레시 토큰 발급 스크립트
(Analytics + Data API 스코프 포함)

사용법:
  1. .env에 YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET 입력
  2. python auth/get_youtube_token.py 실행
  3. 브라우저에서 Google 계정 로그인 및 권한 승인
  4. 출력된 YOUTUBE_REFRESH_TOKEN 값을 .env에 붙여넣기

참고: 기존 sns_uploader에서 youtube.upload 스코프만 사용 중이라면
      이 스크립트로 youtube.readonly + yt-analytics.readonly 스코프를
      추가하여 새 리프레시 토큰을 발급받아야 합니다.
"""

import sys
import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET

import requests

REDIRECT_PORT = 8094
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

auth_code = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        auth_code = query.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            "<html><body><h2>인증 완료! 이 창을 닫으세요.</h2></body></html>".encode()
        )

    def log_message(self, format, *args):
        pass


def main():
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_CLIENT_SECRET:
        print("오류: .env에 YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET을 먼저 입력하세요.")
        sys.exit(1)

    scope_str = " ".join(SCOPES)

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={YOUTUBE_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={quote(scope_str)}"
        "&response_type=code"
        "&access_type=offline"
        "&prompt=consent"
    )

    print("브라우저에서 Google 로그인 페이지를 엽니다...")
    print(f"스코프: {scope_str}")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler)
    print(f"인증 콜백 대기 중 (http://localhost:{REDIRECT_PORT})...")
    server.handle_request()

    if not auth_code:
        print("오류: 인증 코드를 받지 못했습니다.")
        sys.exit(1)

    print("인증 코드 수신 완료. 토큰 교환 중...")

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
    )

    if resp.status_code != 200:
        print(f"토큰 교환 실패: {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    data = resp.json()
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        print("오류: refresh_token을 받지 못했습니다.")
        print("https://myaccount.google.com/permissions 에서 앱 액세스 권한을 해제한 뒤 다시 시도하세요.")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("YouTube 토큰 발급 성공!")
    print("=" * 50)
    print(f"\n아래 값을 .env 파일에 붙여넣으세요:\n")
    print(f"YOUTUBE_REFRESH_TOKEN={refresh_token}")
    print()


if __name__ == "__main__":
    main()
