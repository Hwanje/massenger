# VaultChat Advanced 🔐

> End-to-End Encrypted Secure Messenger with Advanced Admin Security

고급 보안 시스템이 적용된 실시간 채팅 메신저입니다. OTP 기반 방 참가, E2E 암호화, 관리자 2FA 인증 등을 지원합니다.

![Version](https://img.shields.io/badge/version-2.0-blue)
![Security](https://img.shields.io/badge/security-JWT%20%2B%202FA-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## ✨ 주요 기능

### 🔒 보안 기능
- **JWT 토큰 인증**: 관리자 세션의 안전한 인증
- **2FA (TOTP)**: Google Authenticator 기반 두 단계 인증
- **IP 화이트리스트**: 관리자 접속 IP 제한 (선택적)
- **Rate Limiting**: DDoS 및 무차별 대입 공격 방지
- **감사 로깅**: 모든 관리자 행위 기록

### 💬 채팅 기능
- **OTP 초대 코드**: 시간 기반 일회용 비밀번호
- **E2E 암호화**: AES-256 메시지 암호화
- **파일 전송**: 이미지 및 일반 파일 지원 (최대 5MB)
- **실시간 메시지**: Socket.IO 기반 즉시 메시지

### 🛠️ 관리자 패널
- **실시간 통계**: 사용자, 방, 메시지 카운트
- **방 관리**: 활성 방 모니터링 및 강제 폐쇄
- **전역 공지**: 모든 사용자 대상 알림
- **감사 로그**: 관리자 행동 이력 추적
- **강제 퇴장**: 문제 사용자踢出 기능

## 🚀 시작하기

### 사전 요구사항
- Python 3.9+
- Node.js (선택, 로컬 개발용)
- Google Authenticator 앱

### 설치

```bash
# 저장소 복제
git clone https://github.com/Hwanje/messenger.git
cd messenger

# 가상 환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정 (.env 파일 생성)
cp .env.example .env
```

### 환경 변수 설정

```env
# 관리자 설정
ADMIN_ID=admin
ADMIN_PW=your_secure_password
ADMIN_2FA_SECRET=your_base32_secret  # pyotp.generate_base32()로 생성

# 보안 설정
SECRET_KEY=your_random_secret_key
ADMIN_IP_WHITELIST=192.168.1.1,10.0.0.0/24  # 선택적

# Rate Limiting
RATE_LIMIT_WINDOW=60
RATE_LIMIT_MAX_REQUESTS=100
```

### 실행

```bash
# 서버 실행
uvicorn main:socket_app --host 0.0.0.0 --port 8000 --reload

# 또는 Python으로 직접 실행
python main.py
```

### 2FA 시크릿 생성 (초기 설정)

```python
import pyotp
secret = pyotp.random_base32()
print(f"2FA Secret: {secret}")
print(f"TOTP URI: {pyotp.totp.TOTP(secret).provisioning_uri('VaultChat', issuer_name='VaultChat')}")
```

## 📁 프로젝트 구조

```
messenger/
├── main.py              # 백엔드 서버 (FastAPI + Socket.IO)
├── index.html           # 프론트엔드 (모던 UI)
├── requirements.txt     # Python 의존성
├── .env                 # 환경 변수 (생성 필요)
├── vaultchat.db         # SQLite 데이터베이스 (자동 생성)
└── README.md            # 이 문서
```

## 🔐 관리자 접속 가이드

1. **Google Authenticator 설정**
   - QR코드 스캔 또는 시크릿 키 직접 입력
   - 6자리 OTP 코드 생성

2. **관리자 패널 접속**
   - 메인 화면에서 "관리자 패널" 버튼 클릭
   - ID, 비밀번호, 2FA 코드 입력
   - JWT 토큰 발급 및 세션 시작

3. **보안 검사 통과**
   - IP 화이트리스트 설정 시 허용 IP에서만 접속 가능
   - Rate Limit 초과 시 1분 대기 필요

## 🎨 UI 특징

### 다크 모드 디자인
- 모던한 다크 테마
- 부드러운 애니메이션 효과
- 반응형 레이아웃 (모바일 지원)

### 사용자 UX
- OTP 입력 자동 포커스 이동
- 실시간 Toast 알림
- 메시지 타임스탬프
- 파일 미리보기

## 📊 데이터베이스 스키마

### users
| 필드 | 타입 | 설명 |
|------|------|------|
| id | INTEGER | 기본 키 |
| nickname | TEXT | 사용자 닉네임 |
| room | TEXT | 현재 방 |
| ip_address | TEXT | 접속 IP |
| joined_at | TIMESTAMP | 입장 시간 |
| last_active | TIMESTAMP | 마지막 활동 |

### rooms
| 필드 | 타입 | 설명 |
|------|------|------|
| id | INTEGER | 기본 키 |
| name | TEXT | 방 이름 |
| secret | TEXT | OTP 시크릿 |
| creator | TEXT | 방장 닉네임 |
| created_at | TIMESTAMP | 생성 시간 |
| is_active | BOOLEAN | 활성 상태 |
| max_users | INTEGER | 최대 인원 |
| user_count | INTEGER | 현재 인원 |

### admin_logs
| 필드 | 타입 | 설명 |
|------|------|------|
| id | INTEGER | 기본 키 |
| admin_id | TEXT | 관리자 ID |
| action | TEXT | 수행 작업 |
| target | TEXT | 대상 |
| details | TEXT | 상세 내용 |
| ip_address | TEXT | 접속 IP |
| timestamp | TIMESTAMP | 시간 |

## 🔧 API 엔드포인트

### REST API

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| GET | `/` | 서버 상태 확인 |
| GET | `/health` | 헬스 체크 |
| POST | `/api/admin/login` | 관리자 로그인 |
| GET | `/api/admin/stats` | 통계 조회 |
| GET | `/api/admin/logs` | 감사 로그 조회 |

### Socket.IO 이벤트

| 이벤트 | 방향 | 설명 |
|--------|------|------|
| `create_room` | Client→Server | 방 생성 |
| `join_with_otp` | Client→Server | OTP로 참가 |
| `send_secure_msg` | Bidirectional | 암호화 메시지 |
| `admin_auth` | Client→Server | 관리자 인증 |
| `delete_room_admin` | Client→Server | 방 폐쇄 |
| `send_global_notice` | Client→Server | 전역 공지 |
| `kick_user` | Client→Server | 강제 퇴장 |

## 🛡️ 보안 권장사항

1. **비밀번호 관리**
   - 강력한 관리자 비밀번호 사용
   - 정기적인 비밀번호 변경

2. **2FA 필수화**
   - Google Authenticator 권장
   - 백업 코드 안전한 곳에 보관

3. **IP 화이트리스트**
   -IP에서만 관리자 접속 허용
   - VPN 활용 권장

4. **모니터링**
   - 정기적인 감사 로그 검토
   - 이상 행동 탐지

## 📝 라이선스

MIT License - [LICENSE](LICENSE) 파일

## 🤝 기여

버그 리포트 및 기능 요청은 GitHub Issues를 이용해주세요.

## 📧 연락처

- GitHub: [@Hwanje](https://github.com/Hwanje)
- Project: [messenger](https://github.com/Hwanje/messenger)

---

**Made with 🔐 for secure communication**
