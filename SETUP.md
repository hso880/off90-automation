# OFF90 Discord 파이프라인 설정 가이드

## Discord 봇 설정

### 1단계: Discord 개발자 앱 생성

1. https://discord.com/developers/applications 접속
2. **New Application** → 이름 입력 (예: `OFF90 Bot`) → Create
3. 좌측 메뉴 **Bot** 클릭
4. **Reset Token** → 토큰 복사 → `DISCORD_BOT_TOKEN`으로 저장
5. 아래 **Privileged Gateway Intents** 에서
   - **Message Content Intent** → 켜기 ✅
   - Save Changes

### 2단계: 봇 서버 초대

1. 좌측 메뉴 **OAuth2 → URL Generator**
2. Scopes: **bot** 체크
3. Bot Permissions:
   - **Send Messages** ✅
   - **Attach Files** ✅
   - **Embed Links** ✅
   - **Read Message History** ✅
4. 생성된 URL 복사 → 브라우저 열기 → 서버 선택해서 초대

### 3단계: 채널 ID 복사

1. Discord → 사용자 설정(⚙️) → **고급** → **개발자 모드** 켜기
2. 봇이 있는 채널 우클릭 → **채널 ID 복사** → `DISCORD_CHANNEL_ID`로 저장

---

## GitHub Secrets 추가

Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 값 |
|---|---|
| `DISCORD_BOT_TOKEN` | Discord 개발자 포털 봇 토큰 |
| `DISCORD_CHANNEL_ID` | Discord 채널 ID (숫자) |
| `NAVER_CLIENT_ID` | 네이버 개발자 센터 클라이언트 ID |
| `NAVER_CLIENT_SECRET` | 네이버 개발자 센터 시크릿 |

기존 유지 (이미 있어야 함):
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
- `IG_ACCESS_TOKEN`, `IG_BUSINESS_ACCOUNT_ID`

---

## 네이버 이미지 검색 API

1. https://developers.naver.com → 로그인 → **Application → 애플리케이션 등록**
2. 사용 API → **검색** 체크
3. 환경 추가 → WEB 설정 → URL: `https://github.com`
4. **Client ID**, **Client Secret** 복사

---

## Workflow 파일 2개 추가

GitHub 레포 → 상단 **Add file → Create new file**

---

### 파일 1: `.github/workflows/daily_content.yml`

```yaml
name: Daily Content Pipeline

on:
  schedule:
    - cron: '0 23 * * *'   # 매일 오전 8시 KST
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
          DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
          DISCORD_CHANNEL_ID: ${{ secrets.DISCORD_CHANNEL_ID }}
          NAVER_CLIENT_ID: ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: python pipeline_daily.py
```

---

### 파일 2: `.github/workflows/poll_discord.yml`

```yaml
name: Poll Discord

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
          DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
          DISCORD_CHANNEL_ID: ${{ secrets.DISCORD_CHANNEL_ID }}
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

## 사용 흐름

```
매일 오전 8시 KST
  → Discord 채널에 사진 3장 + "1, 2, 3 중 입력" 메시지

사용자: 2
  → 약 60초 후 캐러셀 슬라이드 4장 + 초안 캡션 수신

사용자: (원하는 캡션 직접 입력)
  → "캡션 저장됨" 확인 메시지

사용자: 발행해줘
  → Instagram 업로드 완료 + 링크 수신
```

---

## 상태 머신

```
idle → awaiting_photo → (generating) → awaiting_publish → published → idle
```

상태는 `pending/state.json` 에 자동 저장됩니다.
