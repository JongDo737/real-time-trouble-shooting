# 릴슈 프론트

HTML/CSS/JavaScript 프론트입니다. front-api v1.1과 대화에서 확정한 변경사항을 반영했습니다. 백엔드·RAG·DB 코드는 수정하지 않습니다.

## 실행

Node.js 22 이상에서 실행합니다.

```sh
cd frontend
cp .env.example .env
npm start
```

`.env`에서 실제 브라우저 접속 주소를 설정합니다. 기본 포트는 8080이며, 백엔드 포트와 겹치면 `PORT`를 변경하세요. 주소 변경 후에는 프론트 서버를 다시 실행해야 합니다.

| 환경변수 | 용도 |
|---|---|
| `PORT` | 프론트 서버 포트, 기본 8080 |
| `HOST` | 프론트 서버 바인딩 주소, 기본 0.0.0.0 |
| `API_BASE_URL` | REST 기본 주소. 예: `http://realshoot/backend/api/` |
| `WS_BASE_URL` | STOMP 접속 주소 전체. 예: `ws://realshoot/backend/ws/` |
| `STT_URL` | 음성 변환 주소. 기본 Nginx 경로 `/voice/stt/` |
| `ENABLE_UI_PREVIEW` | `/preview.html` 개발 미리보기 허용, 기본 false |
| `MOCK_ROLE` | 미리보기의 최초 역할. 실제 역할은 로그인 응답으로 결정 |

Docker와 `.env.example`은 Nginx 진입점을 기준으로 `API_BASE_URL=/backend/api/`, `WS_BASE_URL=/backend/ws/`를 사용합니다. 브라우저 접속 주소를 기준으로 API 주소를 만들며, WebSocket 상대 경로는 HTTP에서 `ws:`, HTTPS에서 `wss:`로 변환합니다. WebSocket 주소의 끝 슬래시는 Nginx의 `location /backend/ws/`와 맞춰 리다이렉트 없이 연결합니다. 프론트 서버에 직접 접속하는 경우에는 브라우저에서 접근 가능한 백엔드 절대 주소를 설정하세요.

Nginx는 로그인 요청 `/backend/api/auth/login`을 백엔드 `/api/auth/login`으로, 회원가입 요청 `/backend/api/auth/signup`을 `/api/auth/signup`으로 전달합니다. WebSocket 연결 `/backend/ws/`는 백엔드 `/ws/`로 전달합니다.

실제 주소는 소스에 직접 적지 않습니다. 공개 설정만 `/runtime-config.js`로 전달합니다. JWT 비밀키·비밀번호를 환경변수 공개 설정에 넣지 마세요. Docker 내부 서비스명이 아닌 브라우저가 접속할 수 있는 주소가 필요합니다.

## 인증과 회원가입

기존 쿠키 인증에서 새 API의 Bearer 방식으로 변경했습니다.

- 로그인: `POST auth/login`, 요청 `username`, `password`
- 로그인 응답의 `accessToken`, `user`, 만료 시각을 sessionStorage에 저장
- 실제 `user.role`: ADMIN은 한국어 상담원 화면, USER는 영어 고객 화면
- 비밀번호는 저장하지 않음. 401·만료 시 세션 삭제
- 로그아웃은 서버 실패 여부와 관계없이 세션·소켓·타이머 정리
- 로그인 프로필은 `user.username`, `user.companyName`으로 표시. 선택적 `clientName`, `position`이 있으면 사용하며, 실제 로그인 사용자에게 샘플 이름을 표시하지 않음
- 회원가입은 고객사 전용이며 폼·검증·API 전송에서 `clientName`, `companyName`, `position`, `username`, `password` 사용
- 이름·회사명·직책·아이디는 앞뒤 공백을 제거한 뒤 검증·전송하며, 내부 공백과 비밀번호는 유지
- 첨부 `front-api (2).md`의 A-1은 `companyCode` 방식이지만, 사용자가 현재 백엔드 DTO의 이름·회사명·직책 방식을 명시적으로 선택했으므로 회원가입에 한해 이 규격을 적용. `companyCode`와 snake_case 필드는 보내지 않음
- 이름 20자, 회사명 50자, 직책 30자 이내로 검증. 아이디·비밀번호는 API 명세 기준 검증

## 통화 흐름

1. 고객이 장비명·오류 코드·문제 내용을 `POST calls`로 전송
2. 응답의 UUID `callId`로 STOMP 채널 구독 후 대기
3. 상담원은 `PATCH calls/{callId}/status`에 CALLING 전송
4. 성공 후 채널 구독, 해결방법 REST 조회 시작
5. 상담원만 종료 아이콘 사용. 해결/미해결 선택 후 RESOLVED/UNRESOLVED 전송
6. 종료·부재중 이벤트에서 구독 해제, 임시 메모 폐기, 목록 갱신

PENDING은 서버가 오래 기다린 순으로 정렬합니다. 상태 필터는 명세의 다섯 상태(PENDING/CALLING/MISSED/RESOLVED/UNRESOLVED)를 지원합니다. MISSED는 60초 기준 서버가 변경하며 프론트에서 타이머로 상태를 조작하지 않습니다. 상담원 목록은 5초 간격으로 조회하며 요청이 겹치지 않습니다. 페이지네이션은 서버 응답을 사용합니다.

상태별 건수는 페이지 행 개수가 아닌 상태별 목록 응답의 `totalElements`를 사용합니다. 전체 건수에는 서버의 전체 조회 결과를 사용합니다.

## 통화 ID와 시각

- 목록·상세·REST·소켓 식별자: 백엔드가 제공하는 UUID `callId`
- 현재 통화 DTO는 숫자 `id`를 반환하지 않으므로 화면에서도 UUID를 사용
- 목록의 접수 시간은 `createdAt`으로 `3분 전`처럼 계산. DB에 상대 시간을 저장하지 않음
- 서버의 UTC ISO 값을 유지하고, 화면·툴팁·번역 시각은 브라우저 현지 시간과 시간대로 표시
- 상대 시간은 UTC 시각 차이로 계산하며 1분마다 갱신
- 시간대 없는 문자열이나 초/밀리초 단위가 불명확한 숫자는 해석하지 않음

목록 응답의 `customer.username`은 계정이며 필수 화면 정보로 사용합니다. 선택적 `customer.clientName`이 있으면 이름을 표시하고, 없으면 문의 계정으로 명시해 표시합니다. 상세 응답에 고객 정보가 없으면 같은 문의의 목록 데이터를 유지합니다.

## 소켓 라이브러리 준비

`@stomp/stompjs` 7.5.0을 설치하고 브라우저 파일과 라이선스를 `public/vendor/`에 준비했습니다. 버전은 package.json과 package-lock.json으로 고정했습니다.

새 환경에서는 다음 순서로 같은 버전을 준비합니다.

```sh
npm ci --ignore-scripts
npm run vendor:stomp
```

`vendor:stomp`가 공식 패키지의 브라우저 번들과 라이선스를 `public/vendor/`에 복사합니다. CDN은 사용하지 않습니다. package-lock.json과 public/vendor의 파일도 함께 관리합니다.

`WS_BASE_URL`은 브로커 접속 주소입니다. `/topic/calls/{callId}`는 별도의 STOMP 구독 목적지이며 서버 URL 뒤에 붙이지 않습니다.

- 구독: `/topic/calls/{callId}`
- 텍스트 전송: `/app/calls/{callId}/message`, body `{ text }`
- 연결 헤더: `Authorization: Bearer ...`
- 재연결 3초. 다시 연결되면 상세 조회로 대화 복구
- 내 역할의 번역 이벤트는 무시하고 utteranceId 중복 제거
- 번역 실패·확인 필요 상태를 역할 언어로 표시

## 통화 중 음성 입력

기본 설정 `STT_URL=/voice/stt/`는 다운로드의 `share/voice-ai_code` 예제를 참고한 **MediaRecorder → multipart audio 업로드 → faster-whisper** 방식을 사용합니다. 고객·상담원이 통화로 연결되면 마이크 권한을 요청하고 자동으로 듣습니다. 약 1초의 발화 후 침묵을 감지해 문장을 끊고 서버에서 텍스트로 변환하여 통화 STOMP로 자동 전송합니다. 긴 발화는 최대 30초마다 분할하며, 음성 재생(TTS)은 포함하지 않습니다.

- 고객(USER)은 영어 `en`, 상담원(ADMIN)은 한국어 `ko`. 서버도 JWT 역할과 언어가 일치하는지 검증합니다.
- Nginx `/voice/stt/` → 독립 `voice:8008/stt/`. 기존 백엔드·RAG 코드와 배포는 유지합니다. JWT는 기존 Bearer 토큰을 사용하며 참고 코드의 쿠키·고정 키·issuer 방식은 사용하지 않습니다.
- 음성은 `audio` 파일 필드, 언어는 `language` 필드로 업로드합니다. ffmpeg로 mono 16kHz WAV로 변환하고 CPU int8 faster-whisper tiny 모델로 처리합니다. 모델은 첫 사용 시 내려받아 `whisper_models` 볼륨에 캐시합니다.
- 업로드는 최대 5MiB, 변환된 문장은 최대 2,000자입니다. 임시 음성 파일은 요청 처리 후 삭제하며 음성·인식 텍스트·토큰은 로그에 남기지 않습니다.
- HTTPS 또는 localhost에서 사용합니다. 권한 거부·마이크 없음·서비스 인증/변환 실패는 화면에 안내합니다. 직접 텍스트를 입력·전송하는 기능은 제공하지 않습니다.
- 변환 중에도 다음 문장 녹음을 이어가고, 녹음 파일은 순서대로 전송합니다. 대기 문장은 최대 3개로 제한하며 지연이 심하면 마이크를 중지하고 안내합니다. 음소거 버튼으로 중지하고 마이크 재개 버튼으로 다시 사용할 수 있습니다.
- 통화 종료·로그아웃·소켓 끊김·다른 탭 전환·페이지 이탈 시 마이크와 HTTP 요청을 중지하며, 늦은 결과는 전송하지 않습니다. 재연결·탭 복귀 시 연결된 통화면 자동 재개하되 사용자의 음소거 선택은 유지합니다. 권한 거부/변환 오류 후에는 반복 요청하지 않고 수동 재개를 기다립니다.
- `STT_URL`을 비우면 브라우저 SpeechRecognition을 사용합니다. 이 대체 방식은 확정 문장만 전송하고 브라우저 외부 음성 인식 서비스가 사용될 수 있습니다.

실행: `docker compose up -d --build voice frontend` 후 `docker compose exec nginx nginx -s reload`. 새 환경에서 전체 실행할 때는 `docker compose up -d --build`를 사용합니다.

사용 순서: 고객 문의 접수 → 상담원 수락 → 최초 마이크 권한 허용 → 자동 녹음 시작 → 고객 영어 / 상담원 한국어 발화 → 잠깐 멈춤 → 내 원문·상대 번역문 확인.

## 해결방법

상담원만 `GET calls/{callId}/solution`을 2초마다 조회합니다. PENDING이 아니면 멈추고 답변·출처·페이지·확인 필요·엔지니어 연결 필요 안내를 표시합니다. 실제 엔지니어 연결 API는 만들지 않았습니다. 고객은 해당 API를 호출하거나 매뉴얼을 표시하지 않습니다.

## 미리보기

`ENABLE_UI_PREVIEW=true` 설정 후 `/preview.html` 우측 하단의 ‘화면 미리보기’를 펼쳐 화면을 전환합니다. 이 도구는 본문 공간을 차지하지 않아 운영 화면과 같은 배치를 확인할 수 있습니다. 실제 로그인·통화 요청·소켓 연결은 수행하지 않으며 성공 데이터를 만들지 않습니다. 로그인 화면의 버튼에서 고객사 회원가입 화면도 볼 수 있습니다. 운영에서는 미리보기를 끄세요.

## 파일 역할

| 파일 | 역할 |
|---|---|
| `app.js` | DOM 이벤트·모달·미리보기·텍스트 전송 |
| `support-controller.js` | 로그인·통화·조회·폴링·소켓 생명주기 |
| `views.js` | 화면 HTML |
| `api-client.js`, `support-api.js` | HTTP 요청과 확정된 REST 경로 |
| `session.js` | 세션 보관·만료 |
| `call-channel.js` | STOMP 구독·재연결·중복 제거 |
| `call-data.js` | API 응답과 화면 데이터 변환 |
| `validation.js` | 필드 검증 |
| `config.js`, `service-urls.js` | 환경변수·주소 조합 |
| `utc.js` | UTC ISO 처리·현지 시간 표시·상대 시간 계산 |
| `model.js` | 상태 목록·화면 초기값·목 프로필·HTML 이스케이프 |
| `dom.js` | HTML 문자열·모달 포커스 |

`app.js`가 `support-controller.js`를 직접 사용합니다. 통신 경로는 `support-api.js`와 `call-channel.js`에서 관리합니다.

## Docker

STOMP 파일 준비 후 실행합니다.

```sh
docker build -t rilshu-frontend ./frontend
docker run --rm --env-file ./frontend/.env -p 8080:8080 rilshu-frontend
```

PORT를 변경했다면 매핑도 맞춰야 합니다. 운영 HTTPS·프록시는 배포 담당자와 구성하세요.

## 검증

```sh
npm run check
npm test
```

자동 테스트는 가짜 HTTP·STOMP 클라이언트로 계약과 상태 전환을 검증합니다. 실제 서버 로그인·회원가입·텍스트·소켓·RAG의 종단 간 동작은 실제 서버 주소 설정 후 확인해야 합니다. 설치한 실제 STOMP 브라우저 번들로 인증 헤더·구독·전송·정상 해제를 로컬 가상 연결에서 확인했습니다. 현재 통화 DTO는 UUID `callId`를 제공하며 프론트도 이 값을 표시합니다.

STOMP 클라이언트의 연결·구독·해제 API는 [공식 문서](https://stomp-js.github.io/api-docs/latest/classes/Client.html)를 기준으로 작성했습니다.

## 현재 백엔드와의 연결 규격

첨부 `front-api (2).md` v1.1을 기준으로 프론트를 맞췄습니다. 회원가입만 사용자가 확인한 현재 백엔드 DTO의 `clientName`, `companyName`, `position` 방식을 적용합니다. 실제 배포 서버에서의 종단 간 검증은 별도로 필요합니다.

| 항목 | 프론트 적용 |
|---|---|
| 회원가입 | `clientName`, `companyName`, `position`, `username`, `password` |
| 로그인 사용자 | 명세의 `user.id`, `user.username`, `user.role`, `user.companyName`만 있어도 표시. 이름·직책은 선택 정보 |
| 문의 고객 | `customer.username`, `customer.companyName`으로 표시하며 이름·직책이 없는 명세 응답도 지원 |
| 통화 ID | UUID `callId`를 표시·전송 |
| 상세 | 목록에서 고객·증상 정보를 보존하고 상세의 `messages`를 조회자 언어로 표시 |
| 통화 복구 | 로그인·새로고침 시 진행 중 목록을 조회. 고객은 본인 PENDING/CALLING, 상담원은 `agent.id`가 본인인 CALLING만 복구 |
| RAG | `PENDING`, `found`, `not_found`, `error` 및 `answer`, `sources`, `needsReview`, `handoff` 처리. 출처만 있는 `found`도 완료로 표시 |
| STOMP | CONNECT의 Bearer 토큰, `/topic/calls/{callId}` 구독, `/app/calls/{callId}/message`에 `{text}` 전송 |
| 오류 | 서버 규격 `error.request_id`를 프론트의 `requestId`로 변환. 중복 아이디·식별 가능한 422 필드 오류는 입력란에 표시 |
| 상태 건수 | 상태별 목록의 `totalElements` 사용 |

REST 요청은 DB 컬럼 이름으로 바꾸지 않습니다. 장비·이슈는 명세의 `equipmentName`, `errorCode`, `symptom`으로 전송합니다. RAG는 백엔드가 처리하며 프론트는 본사용 해결방법 REST API만 조회합니다.

음성 인식 결과만 컨트롤러 내부 전송 함수를 통해 기존 번역 소켓으로 전달합니다.

통화 생성 직후 UUID를 저장하고 구독합니다. 상세 조회가 실패해도 접수한 통화를 유지하며, 재연결 때 상세를 다시 조회합니다. 세션 종료나 페이지 종료 후 늦게 도착한 응답은 무시하고 타이머와 요청을 정리합니다.

## 글꼴

Pretendard 1.3.9의 가변 WOFF2 폰트를 `public/assets/fonts/pretendard/`에서 직접 제공합니다. 제목은 600, 기본 버튼은 500, 본문은 400을 사용합니다. 외부 폰트 CDN은 호출하지 않습니다. Docker에서도 public 디렉터리와 함께 포함됩니다.

원본 출처와 SIL Open Font License 1.1은 폰트 폴더의 README.txt와 LICENSE.txt에 보관합니다. 폰트 바이너리는 수정하지 않았습니다.
