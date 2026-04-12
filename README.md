# K-ESG AI Platform (KESGAI)

대한민국 중소·중견기업 및 기관을 위한 AI 기반 맞춤형 ESG 보고서 자동 생성 플랫폼입니다. DeepSeek AI 엔진을 활용하여 신속하고 전문적인 ESG 가이드라인 및 보고서 초안을 제공합니다.

## 🚀 주요 기능
- **1단계 (초도 분석)**: 기업명과 업종 기반의 고속 ESG 경영 초안 생성 (약 10초 소요)
- **2단계 (심층 분석)**: 기업별 상세 현황 데이터를 매핑한 정밀 ESG 분석 (약 180초 소요)
- **리포트 자동화**: 완성된 분석 결과를 DOCX 및 PDF 형식으로 즉시 다운로드 가능
- **K-ESG 최적화**: 국내 ESG 공시 가이드라인에 최적화된 용어 및 문체 사용

## 🛠️ 시스템 아키텍처
- **Frontend**: Vanilla JS, HTML5, CSS3 (Premium Dark UI)
- **Backend API**: FastAPI (Python 3.12)
- **Worker**: Async Task Queue (Redis 기반 비동기 처리)
- **AI Engine**: DeepSeek-V3 API
- **Infrastructure**: Docker & Docker Compose

## 📦 설치 및 시작 가이드

명령어 몇 줄만으로 시스템을 다른 환경에 즉시 복제하고 실행할 수 있습니다.

### 1. 전제 조건
- Docker 및 Docker Compose 가 설치되어 있어야 합니다.
- [DeepSeek Platform](https://platform.deepseek.com/) API 키가 필요합니다.

### 2. 저장소 클론 및 설정
```bash
git clone https://github.com/jongjean/esgai.git
cd esgai

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 DEEPSEEK_API_KEY를 입력하세요.
```

### 3. 시스템 구동
```bash
# 필요한 디렉토리 생성 (최초 1회)
mkdir -p downloads storage/reports

# 도커 컨테이너 빌드 및 실행
docker compose up -d --build
```

### 4. 접속
- **사용자 UI**: `http://localhost:4600`
- **엔진 API**: `http://localhost:4610`

## 🛡️ 라이선스 및 보안
- 본 프로젝트는 보안을 위해 API 키가 포함된 `.env` 파일을 저장소에 포함하지 않습니다.
- 생성된 데이터는 `downloads/` 및 `storage/` 폴더에 로컬로 보관됩니다.

---
© 2026 Korea ESG Association AI (KESGAI). All rights reserved.
