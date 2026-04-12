# ✨ ESG ai 프론트엔드 디자인 시스템 및 구축 명세 (Aesthetic Spec)

본 문서는 **esgai** 플랫폼의 얼굴인 프론트엔드를 구축함에 있어, 최상의 미학적 완성도와 사용자 경험을 보장하기 위한 디자인 가이드라인입니다.

---

## 🎨 1. 핵심 비주얼 아이덴티티 (Visual Identity)

### 💎 디자인 컨셉: "Eco-Tech Synergy"
- **기조**: "나, 너, 회사, 사회"가 연결되는 가치의 시너지(Synergy)와 인공지능 기술의 융합.
- **핵심 문구**: **"나 너 회사 사회의 가치를 알면 이미 당신은 ESG실천가입니다."**
- **브랜드 로고**: 사용자 제공 '나너회사사회' 크로스 심볼을 헤리티지 심볼로 활용.
- **핵심 스타일**: **글래스모피즘(Glassmorphism)**
  - 배경 위에 투명한 레이어를 띄워 깊이감과 현대적인 감각을 동시에 전달.
  - 리포트 카드 및 입력 폼에 `backdrop-filter: blur(10px)`를 적극 활용.

### 🎨 컬러 팔레트 (Color Palette)
- **Primary-Dark**: `#0F172A` (Deep Navy - 신뢰의 기반)
- **Point-Green**: `#008000` (Logo Green - 실천과 성장의 에메랄드)
- **Point-Blue**: `#0000FF` (Logo Blue - 전문성과 기술의 일렉트릭 블루)
- **Text-Bright**: `#F8FAFC` (Ghost White - 높은 가독성)

### 🖋️ 타이포그래피 (Typography)
- **Font-Family**: Google Fonts의 **'Outfit'** (헤드라인용), **'Inter'** (본문용).
- **Scale**: 가독성을 위한 여유로운 행간과 크기 대비(Hierarchy) 적용.

---

## ⚡ 2. 테크니컬 스택 및 로직 (Technical Implementation)

| 구분 | 선택 기술 | 기대 효과 |
| :--- | :--- | :--- |
| **언어 (Core)** | Vanilla JS (ESM) | 별도의 빌드 과정 없는 쾌속 로딩 및 유지보수성 |
| **스타일링** | Modern CSS3 (Variables) | 전역 테마 관리 및 애니메이션 구현의 유연성 |
| **레이아웃** | Flexbox & Grid | 모든 기기 환경(모바일/데스크톱)에서의 완벽한 대응 |
| **애니메이션** | CSS Keyframes & Framer-like CSS | 부드러운 트랜지션 및 마이크로 인터랙션 확보 |

---

## 🏗️ 3. 페이지별 디자인 상세 명세

### **A. 랜딩 페이지 (Landing Experience)**
- **Hero Section**: 웅장한 대기 배경 위에 사용자 제공 로고가 중앙에 배치되며, 하단에 **"나 너 회사 사회의 가치를 알면 이미 당신은 ESG실천가입니다."** 캐치프레이즈가 타이핑 애니메이션으로 등장.
- **Value Card**: 서비스의 3단계 가치(생성-결제-리포트)를 입체적인 카드 UI로 표현.

### **B. 생성 및 결제 대시보드 (Functional UX)**
- **Progress Bar**: AI 분석 단계를 시각화하는 부드러운 게이지.
- **Payment Lock**: 결제 전 리포트가 블러(Blur) 처리된 미리보기 카드로 노출되어 유료 전환 유도.

### **C. 관리자 모드 (Admin Dashboard)**
- **Dark Mode Standard**: 눈의 피로를 최소화하는 정교한 다크 테마 적용.
- **Data Table**: 간결하고 정돈된 데이터 열과 직관적인 액션 버튼.

---
*최종 업데이트: 2026-04-08 (Premium Aesthetic Plan 확정)*
