# 실시간 장비 트러블슈팅

글로벌 고객의 영어 문의와 한국 상담원의 한국어 응대를 실시간으로 잇고, 장비 매뉴얼에서 해결 방법을 찾는 시스템입니다.

## 주제

- 실시간 통화 연결과 번역·매뉴얼 검색

## 도메인

- **범위**: 반도체 전공정 유지보수
- **사용자**: 고객사 엔지니어와 상담원
- **데이터**: 에러 규격·현장 로그·위험도

## Overview

- **목적**: 장비명·에러 코드로 접수한 문의를 통화로 연결하고, 번역과 매뉴얼 검색으로 응대를 돕습니다
- **방법**: Nginx 단일 진입점 아래 프론트, Spring 백엔드, Whisper 음성 변환, FAISS RAG를 붙입니다

고객은 영어 화면에서 문의를 넣고, 상담원은 한국어 화면에서 통화를 받습니다. 역할은 회원가입 시 `USER`, 기동 시 만들어 두는 테스트 계정만 `ADMIN`입니다.

## Features

- 장비·에러 코드는 매뉴얼에 있는 값만 선택해 접수
- 통화 중 음성을 텍스트로 바꾼 뒤 상대 언어로 번역
- 접수한 장비·오류·증상을 FAISS에서 검색해 상담원에게 매뉴얼 근거를 표시
- 상담원 테스트 계정 `admin` / `test1234`는 백엔드 기동 시 한 번 생성

## Tech Stack

- Frontend: HTML / JavaScript, STOMP
- Backend: Spring Boot, JWT, MariaDB
- Voice: Whisper
- RAG: FastAPI, FAISS, OpenAI
- Deploy: Docker Compose, Nginx

## Architecture

고객사 화면에서 문의를 넣고 통화를 요청하면, 한국 상담원이 받아 번역 채널과 매뉴얼 검색을 같이 봅니다.

![실시간 통역과 매뉴얼 RAG 흐름](docs/architecture.png)


## System Architecture

```mermaid
flowchart TD
    A[고객 문의] --> B[Nginx :80]
    B --> C[Frontend]
    B --> D[Spring Backend]
    B --> E[Whisper STT]
    D --> F[MariaDB]
    D --> G[FastAPI RAG]
    C --> D
    C --> E
    G --> H[FAISS 매뉴얼]
```

## Directory Structure

```
├── frontend/       # 고객·상담원 화면
├── backend/        # 인증, 통화, 번역 요청
├── fastapi/        # 매뉴얼 RAG
├── voice/          # 음성 변환
├── rag_pipeline/   # 매뉴얼과 FAISS 인덱스 빌드
├── nginx/          # 단일 진입점
├── docker-compose.yml
├── build.sh
└── .env.example
```

## Usage

```sh
cp .env.example .env    # MYSQL_*, JWT_SECRET, OPENAI_API_KEY 입력
./build.sh              # FAISS, Gradle, npm 빌드 후 컨테이너 기동
```

브라우저에서 `http://localhost`로 접속합니다. 상담원 화면은 `admin` / `test1234`, 고객 화면은 회원가입으로 만든 계정으로 로그인합니다.

## 발전 방향

기존 IT 운영 플랫폼에 반도체 장비 특화 AI 상담 모듈로 연동합니다.

- **연동**: ITSM, IT Helpdesk, IT Incident에 API로 붙입니다. 모듈은 반도체 장비 RAG와 다국어 상담을 담당합니다
- **지식 축적**: 상담원 피드백(해결 방법·답변 평가) → 사례 등록(LLM 요약·엔지니어 검수) → 주기적 인덱스 재빌드 → 실제 문의를 평가셋에 추가. 검증 결과와 현장 피드백은 다음 개선에 반영합니다
- **참고 사례**: ServiceNow의 Moveworks 인수 계약(2025.03.10, 발표액 28.5억 달러). AI 어시스턴트와 기업 검색을 업무 플랫폼에 결합한 사례이며, 발표액은 플랫폼 개발비와 구분합니다
