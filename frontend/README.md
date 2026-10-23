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
| `ENABLE_UI_PREVIEW` | `/preview.html` 개발 미리보기 허용, 기본 false |
| `MOCK_ROLE` | 미리보기의 최초 역할. 실제 역할은 로그인 응답으로 결정 |

실제 주소는 소스에 직접 적지 않습니다. 공개 설정만 `/runtime-config.js`로 전달합니다. JWT 비밀키·비밀번호를 환경변수 공개 설정에 넣지 마세요. Docker 내부 서비스명이 아닌 브라우저가 접속할 수 있는 주소가 필요합니다.

## 인증과 회원가입

기존 쿠키 인증에서 새 API의 Bearer 방식으로 변경했습니다.

- 로그인: `POST auth/login`, 요청 `username`, `password`
- 로그인 응답의 `accessToken`, `user`, 만료 시각을 sessionStorage에 저장
- 실제 `user.role`: ADMIN은 한국어 상담원 화면, USER는 영어 고객 화면
- 비밀번호는 저장하지 않음. 401·만료 시 세션 삭제
- 로그아웃은 서버 실패 여부와 관계없이 세션·소켓·타이머 정리
- 이름·사진 목데이터는 유지하되, 실제 `client_name`이 응답에 있으면 실제 이름을 우선 표시
- 회원가입은 고객사 전용이며 `client_name`, `company_name`, `position`, `username`, `password` 전송
- 사용자 확인에 따라 `companyCode`는 제거
- 이름 20자, 회사명 50자, 직책 30자 이내로 검증. 아이디·비밀번호는 API 명세 기준 검증

## 통화 흐름

1. 고객이 장비명·오류 코드·문제 내용을 `POST calls`로 전송
2. 응답의 UUID `callId`로 STOMP 채널 구독 후 대기
3. 상담원은 `PATCH calls/{callId}/status`에 CALLING 전송
4. 성공 후 채널 구독, 해결방법 REST 조회 시작
5. 상담원만 종료 아이콘 사용. 해결/미해결 선택 후 RESOLVED/UNRESOLVED 전송
6. 종료·부재중 이벤트에서 구독 해제, 임시 메모 폐기, 목록 갱신

PENDING은 서버가 오래 기다린 순으로 정렬합니다. 상태 필터에는 CALLING이 없습니다. MISSED는 60초 기준 서버가 변경하며 프론트에서 타이머로 상태를 조작하지 않습니다. 상담원 목록은 5초 간격으로 조회하며 요청이 겹치지 않습니다. 페이지네이션은 서버 응답을 사용합니다.

상태별 건수는 페이지 행 개수가 아닌 상태별 목록 응답의 `totalElements`를 사용합니다. 전체 건수에는 서버의 전체 조회 결과를 사용합니다.

## 숫자 ID와 시각

- 화면 접수 번호: DB의 자동 증가 숫자 `id`
- 내부 REST·소켓 식별자: UUID `callId`
- API가 숫자 `id`를 주지 않으면 `—` 표시. 프론트에서 번호 생성하지 않음
- 목록의 접수 시간은 `createdAt`으로 `3분 전`처럼 계산. DB에 상대 시간을 저장하지 않음
- 정확한 시각은 UTC 기준 `time`의 title에서 확인. 상대 시간은 1분마다 갱신
- 번역 시각도 UTC+0으로 표시하며 브라우저 현지 시간으로 바꾸지 않음
- 시간대 없는 문자열이나 초/밀리초 단위가 불명확한 숫자는 해석하지 않음

목록 응답의 `customer.username`은 로그인 아이디이고 `customer.client_name`은 실제 문의자 이름입니다. 이름이 없으면 아이디를 이름으로 대신 표시하지 않습니다. 상세 응답에 고객 정보가 없으면 같은 문의의 목록 데이터를 유지합니다.

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

## 이미 인식된 음성 텍스트 전달

이번 구현에서는 녹음·STT를 새로 수행하지 않습니다. 음성 담당 코드가 최종 인식 문자열을 아래 함수에 전달합니다.

```js
import { sendRecognizedText } from './js/app.js';
const sent = sendRecognizedText(recognizedText);
```

성공 시 true를 반환하고 내 말을 즉시 표시합니다. 미연결·빈 텍스트·2000자 초과·전송 실패는 false입니다. 별도의 음성 이벤트명이나 파이프라인 주소를 만들지 않았습니다.

## 해결방법

상담원만 `GET calls/{callId}/solution`을 2초마다 조회합니다. PENDING이 아니면 멈추고 답변·출처·페이지·확인 필요·엔지니어 연결 필요 안내를 표시합니다. 실제 엔지니어 연결 API는 만들지 않았습니다. 고객은 해당 API를 호출하거나 매뉴얼을 표시하지 않습니다.

## 미리보기

`ENABLE_UI_PREVIEW=true` 설정 후 `/preview.html` 우측 하단의 ‘화면 미리보기’를 펼쳐 화면을 전환합니다. 이 도구는 본문 공간을 차지하지 않아 운영 화면과 같은 배치를 확인할 수 있습니다. 실제 로그인·통화 요청·소켓 연결은 수행하지 않으며 성공 데이터를 만들지 않습니다. 로그인 화면의 버튼에서 고객사 회원가입 화면도 볼 수 있습니다. 운영에서는 미리보기를 끄세요.

## 파일 역할

| 파일 | 역할 |
|---|---|
| `app.js` | DOM 이벤트·모달·미리보기·인식 텍스트 진입점 |
| `support-controller.js` | 로그인·통화·조회·폴링·소켓 생명주기 |
| `views.js` | 화면 HTML |
| `api-client.js`, `support-api.js` | HTTP 요청과 확정된 REST 경로 |
| `session.js` | 세션 보관·만료 |
| `call-channel.js` | STOMP 구독·재연결·중복 제거 |
| `call-data.js` | API 응답과 화면 데이터 변환 |
| `validation.js` | 필드 검증 |
| `config.js`, `service-urls.js` | 환경변수·주소 조합 |
| `utc.js` | UTC·상대 시간 표시 |
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

자동 테스트는 가짜 HTTP·STOMP 클라이언트로 계약과 상태 전환을 검증합니다. 실제 서버 로그인·회원가입·음성·소켓·RAG의 종단 간 동작은 실제 서버 주소 설정 후 확인해야 합니다. 설치한 실제 STOMP 브라우저 번들로 인증 헤더·구독·전송·정상 해제를 로컬 가상 연결에서 확인했습니다. DB 스키마의 이중 PRIMARY KEY 선언과 응답의 숫자 id 제공 여부는 백엔드 확인이 필요합니다.

STOMP 클라이언트의 연결·구독·해제 API는 [공식 문서](https://stomp-js.github.io/api-docs/latest/classes/Client.html)를 기준으로 작성했습니다.

## 백엔드 연결 전 확인할 항목

현재 검증은 코드와 제공 명세의 대조이며 실제 서버 연동 완료를 뜻하지 않습니다.

| 항목 | 프론트 적용 | 백엔드 확인 필요 |
|---|---|---|
| 회원가입 | `client_name`, `company_name`, `position`, `username`, `password` | 기존 문서의 `companyCode`를 제거하고 이 다섯 필드로 받는지 |
| 실제 이름·직책 | 로그인은 `user.client_name/position`, 문의는 `customer.client_name/position` 사용 | 로그인·목록·상세의 실제 응답에 포함되는지 |
| 접수 번호 | 숫자 `id`, 통신은 UUID `callId` | 목록·상세에 두 값이 모두 포함되는지 |
| 상세의 고객·이슈 | 목록에서 연 문의는 기존 고객 정보·이슈 유지 | 새로고침 후 복구에도 필요하므로 상세에 `customer`, `symptom`, `messages` 제공 여부 |
| 시각 | 시간대가 명시된 ISO 문자열, UTC 표시 | DB DATETIME을 UTC로 직렬화하는지 |
| 입력 오류 | 프론트 필드 검증, 서버 422는 공통 안내 | 특정 입력란에 표시하려면 필드별 오류 응답 형식 합의 필요 |
| 상태 건수 | 상태별 목록의 `totalElements` 사용 | 별도 집계 API는 명세에 없으므로 새 경로를 만들지 않음 |

REST 요청은 DB 컬럼 이름으로 바꾸지 않습니다. 장비·이슈는 명세의 `equipmentName`, `errorCode`, `symptom`으로 전송합니다. RAG는 백엔드가 처리하며 프론트는 본사용 해결방법 REST API만 조회합니다.

통화 생성 직후 UUID를 저장하고 구독합니다. 상세 조회가 실패해도 접수한 통화를 유지하며, 재연결 때 상세를 다시 조회합니다. 세션 종료나 페이지 종료 후 늦게 도착한 응답은 무시하고 타이머와 요청을 정리합니다.

## 글꼴

Pretendard 1.3.9의 가변 WOFF2 폰트를 `public/assets/fonts/pretendard/`에서 직접 제공합니다. 제목은 600, 기본 버튼은 500, 본문은 400을 사용합니다. 외부 폰트 CDN은 호출하지 않습니다. Docker에서도 public 디렉터리와 함께 포함됩니다.

원본 출처와 SIL Open Font License 1.1은 폰트 폴더의 README.txt와 LICENSE.txt에 보관합니다. 폰트 바이너리는 수정하지 않았습니다.
