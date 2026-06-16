# OFF90 텔레그램 파이프라인 설정 가이드

## 사전 준비

### 1. 레포 Public 전환
Settings → General → Danger Zone → Change visibility → Public

### 2. Telegram 봇 생성
1. Telegram에서 @BotFather 검색
2. `/newbot` 입력
3. 봇 이름 설정 (예: OFF90 Bot)
4. **BOT_TOKEN** 복사 (형식: `1234567890:AAF...`)

**CHAT_ID 확인:**
```
https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
```
봇에게 아무 메시지 보낸 후 위 URL 열면 `"chat": {"id": 숫자}` 확인

### 3. 네이버 개발자 센터
1. https://developers.naver.com → 애플리케이션 등록
2. 사용 API: **검색** 체크
3. **NAVER_CLIENT_ID**, **NAVER_CLIENT_SECRET** 복사

---

## GitHub Secrets 추가

Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 값 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather에서 받은 토큰 |
| `TELEGRAM_CHAT_ID` | getUpdates에서 확인한 숫자 |
| `NAVER_CLIENT_ID` | 네이버 앱 클라이언트 ID |
| `NAVER_CLIENT_SECRET` | 네이버 앱 시크릿 |

기존 시크릿 (이미 있어야 함):
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
- `IG_ACCESS_TOKEN`, `IG_BUSINESS_ACCOUNT_ID`

---

## Workflow 파일 추가

> ⚠️ PAT 권한 문제로 워크플로우 파일은 직접 추가해야 합니다.

### 방법
GitHub 레포 → **Actions** 탭 → New workflow → Set up a workflow yourself

또는 로컬에서:
```bash
mkdir -p .github/workflows
```

---

### 파일 1: `.github/workflows/daily_content.yml`

```yaml
name: Daily Content Pipeline

on:
  schedule:
    - cron: '0 23 * * *'   # 매일 오전 8시 KST (UTC 23:00 전날)
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: 패키지 설치
        run: pip install requests deep-translator instaloader

      - name: 파이프라인 실행
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          NAVER_CLIENT_ID: ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: python pipeline_daily.py
```

---

### 파일 2: `.github/workflows/poll_telegram.yml`

```yaml
name: Poll Telegram

on:
  schedule:
    - cron: '*/5 * * * *'   # 5분마다
  workflow_dispatch:

jobs:
  poll:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: 패키지 설치
        run: pip install requests playwright cloudinary

      - name: Playwright 설치
        run: playwright install chromium --with-deps

      - name: 응답 처리
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          CLOUDINARY_CLOUD_NAME: ${{ secrets.CLOUDINARY_CLOUD_NAME }}
          CLOUDINARY_API_KEY: ${{ secrets.CLOUDINARY_API_KEY }}
          CLOUDINARY_API_SECRET: ${{ secrets.CLOUDINARY_API_SECRET }}
          IG_ACCESS_TOKEN: ${{ secrets.IG_ACCESS_TOKEN }}
          IG_BUSINESS_ACCOUNT_ID: ${{ secrets.IG_BUSINESS_ACCOUNT_ID }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: python pipeline_respond.py
```

---

## 테스트 순서

1. Actions → Daily Content Pipeline → Run workflow (수동 실행)
2. Telegram 봇에서 사진 3장 + 버튼 수신 확인
3. 번호 탭 → 60초 대기 → 캐러셀 미리보기 수신 확인
4. "발행해줘" 입력 → Instagram 확인

---

## 상태 머신

```
idle
  └─[매일 8시]→ awaiting_photo (사진 3장 텔레그램 발송)
                  └─[번호 탭]→ generating_carousel (Playwright 렌더)
                                └─[완료]→ awaiting_publish (미리보기 발송)
                                            └─[발행해줘]→ published → idle
```
