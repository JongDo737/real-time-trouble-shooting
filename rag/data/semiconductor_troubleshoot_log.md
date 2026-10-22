# SEMICONDUCTOR FIELD TROUBLESHOOTING LOGS & CASE HISTORY
문서 번호: FIELD-LOG-SEMI-2026-V1
작성: 글로벌 FSE 기술지원팀 & 팹 유지보수팀 현장 노하우 아카이브

---

## [CASE-01] 13.56MHz RF 식각 반사파 12% 스파이크 및 오토 매처 튜닝 불안정
- 설비 및 챔버: 300mm Dry Etch Chamber #4 (AE Cesar 1312 + Seren MC2)
- 현상 보고:
  식각 공정 진행 중 별도 인터록 트립은 안 나는데 13.56MHz RF 제너레이터의 반사파(Reflected Power)가 정상치(<5%)를 벗어나 12%까지 간헐적 스파이크 발생. 
  오토 매처가 헌팅하면서 위상/크기 튜닝을 못 잡고 흔들림.
- 실제 현장 조치 내역 (FSE Senior Kim):
  1. 안전 절차: SEMI S2/S8 준수하여 10,000 AIC 차단기 OFF 및 AC 전원 분리 확인.
  2. 매처 내부 점검 결과, 가변 커패시터(Variable Capacitor) 플레이트에 미세 아킹 흔적(Arcing marks) 및 모터 구동축에 갈리는 소음 확인되어 세정 및 가동 범위 점검.
  3. 은도금(Silver-plated) RF 단자 연결 볼트가 열화로 풀려 있어 규정 토크(4.5 Nm)로 재체결.
  4. 급전선 반사 손실(Return Loss) -14 dB 복구 확인 후, 45분간 챔버 시즈닝 레시피 가동 ➔ 모니터 웨이퍼 투입 결과 반사파 2.3%로 안정화.
- 출처: `Field_Troubleshoot_Report_Etch_202608.pdf p.3`

---

## [CASE-02] 알람 코드 없는 플라즈마 점화 실패(Won't Ignite) 6단계 격리 조치
- 설비 및 챔버: ICP-RIE 300mm 에처 챔버
- 현상 보고:
  레시피 시작 버튼을 눌렀으나 에러 알람 코드가 전혀 뜨지 않은 상태에서 플라즈마가 아예 켜지지 않음(Won't ignite).
- 선배 엔지니어 해결 노하우 (의사결정 트리):
  1. MFC 가스 유량이 실제로 흐르고 있는지 챔버 압력 상승으로 1차 확인.
  2. 챔버 점화 압력이 20~200 mTorr 윈도우 내에 있는지 점검 (스로틀 밸브 및 바라트론 게이지 정상 확인).
  3. RF Forward 파워 인가 및 반사파 50% 초과 여부 확인.
  4. 챔버 오픈 점검 결과, 코일과 진공을 분리하는 석영 유전체 윈도우(Quartz Dielectric Window) 표면에 두꺼운 반응 생성물 코팅 및 0.6mm 식각 마모 발견.
  5. 윈도우 신품 교체 후 Ar 가스 150 mTorr 고압 점화 테스트 실행 ➔ 플라즈마 정상 점화 확인 및 공정 재개.
- 출처: `Field_Troubleshoot_Report_Plasma_202609.pdf p.7`

---

## [CASE-03] 가스 박스 MFC 유량 출렁거림(헌팅) 및 간헐적 AL40 알람 해결
- 설비 및 라인: CVD Gas Box Line #2 (Brooks GF40 Series MFC)
- 현상 보고:
  가스 유량이 셋포인트 부근에서 계속 출렁거리는 헌팅(Hunting/Oscillation) 현상이 발생하고, 간헐적으로 AL40(Excessive flow rate) 경고가 교차 발생.
- 현장 점검 및 해결 절차:
  1. MFC 자체 결함이 아니라, 공통 가스 매니폴드를 공유하는 인접 챔버 동시 가스 호출에 의한 인렛 압력 섭동 확인.
  2. 레귤레이터를 2 psig 단위로 미세 상향 조정(Adjust inlet pressure up by 2 psig)하자 유량 헌팅 현상 즉시 소멸.
  3. 제어 밸브 양단 압력 평형을 맞춘 뒤, Zero 버튼을 5초 이상 길게 눌러 영점을 재설정함.
  4. 이후 유량 오차 ±0.5% 이내로 안정화되어 MFC 교체(RMA) 없이 정상 가동.
- 출처: `Field_Troubleshoot_Report_Gas_202609.pdf p.12`

---

## [CASE-04] 정기 PM 중 안전 인터록 우회(Defeat) 및 EMO 오작동 복구
- 설비 및 상황: Fab 식각 장비 정기 예방 정비(PM)
- 상황 보고:
  엔지니어가 챔버 내부 구동부를 육안 확인하기 위해 도어 인터록을 바이패스(Defeat)하려 함. 작업 중 실수로 EMO 버튼을 누름.
- 안전 관리 규정 적용 조치:
  1. SEMI S2 규정에 따라 테이프나 임의 점퍼선 우회는 불가하며, 인가된 전용 도구(Tool)를 사용해 관리자 입회하에 우회 모드 진입.
  2. EMO 버튼이 눌렸을 때 240 VA 초과 고전압이 즉시 차단되었음을 확인.
  3. EMO 버튼을 당겨서 원위치시켜도 전원이 바로 켜지지 않는 것은 정상 안전 설계(SEMI S2 12.2)이므로, 전장 제어반의 수동 리셋(Manual Reset) 스위치를 조작하여 메인 파워 재인가 완료.
- 출처: `Field_Safety_Audit_Log_202610.pdf p.4`

---

## [CASE-05] 정전척(ESC) 헬륨 리크율 초과 및 DC 셀프 바이어스 18% 편차
- 설비 및 챔버: ICP High Density Etch System
- 현상 보고:
  웨이퍼 후면 헬륨 냉각 라인 리크율(Helium leak-up rate) 알람이 뜨고, 공정 모니터링 상 DC Self-bias 전압이 기준선 대비 18% 튀는 현상 발생.
- 현장 조치 내역:
  1. 잔류 전하 방전 및 위험 에너지 격리(LOTO) 후 챔버 오픈.
  2. 하부 실리콘 전극 표면 검사 결과, 플라즈마 충격에 의한 미세 피팅(Pitting)과 전극 두께 12% 손실(기준 10% 초과) 확인.
  3. 실리콘 전극 신품 교체 및 ESC 세정 진행 후 [Helium Leak Check] 자동화 진단 실행 ➔ 헬륨 누설률 기준치 이하 정상 회복.
- 출처: `Field_Troubleshoot_Report_Chamber_202608.pdf p.19`

---

## [CASE-06] 웨이퍼 이송 로봇(WHR) 'Out of Pocket' 위치 에러 및 재티칭
- 설비: Cluster Tool Vacuum Transfer Module (SCARA Robot)
- 현상 보고:
  로봇 암이 프로세스 챔버에서 웨이퍼를 꺼내는 중 'Out of Pocket' 알람 발생하며 정지.
- 현장 분석 및 조치:
  1. 블레이드 중앙 홀을 지나는 4개 광학 검출 센서 판정 결과, 웨이퍼가 허용 범위를 벗어난 Condition 4(보정 불가 이탈)로 판정되어 설비 자동 셧다운.
  2. 수동 모드로 전환 후 웨이퍼 안전 회수.
  3. 매뉴얼 Section 5.9.1에 따라 증분형 엔코더 호밍(Homing Procedure)을 실행하고, Section 5.9.2에 따라 홈 오프셋을 재설정.
  4. Liveman Teach 펜던트로 챔버 스테이션 재티칭 완료 후 더미 웨이퍼 25매 연속 이송 테스트 통과.
- 출처: `Field_Troubleshoot_Report_Robot_202607.pdf p.8`

---

## [CASE-07] 프로세스 챔버 리크 체크 실패 및 슬릿 밸브 부품 교체
- 설비: 300mm 진공 이송-프로세스 챔버 격리 슬릿 밸브
- 현상 보고:
  정기 리크 체크(Section 7.5.1) 중 베이스 압력 상승률이 허용 기준을 초과하여 진공 불량 발생.
- 현장 조치 및 부품 발주:
  1. 서비스 모드 진입 시 슬릿 밸브/클램프 인터록이 해제되므로 손 끼임 방지 조치 후 점검.
  2. 공압 피팅 에어 누설 점검 후 슬릿 밸브 씰 마모 확인.
  3. 자재 카탈로그 조회하여 정품 파트 넘버 발주: Slit Valve Actuator Seal `AMAT 0190-09539`, Door Liner `P/N 0021-09718` 신품 교체.
  4. 교체 후 헬륨 리크 검사 결과 1.0 x 10^-9 Torr·L/s 이하 달성으로 진공 정상 복구.
- 출처: `Field_Troubleshoot_Report_Vacuum_202609.pdf p.15`

---

## [CASE-08] 배기 덕트 정비 중 VESDA 연기 감지기 오알람 방지 및 격리 절차
- 작업 위치: 서브팹 배기 라인(Exhaust Line)
- 작업 상황:
  배기 덕트 정비 중 분진으로 인해 흡입형 연기 감지기(VESDA)가 작동하면 팹 전체 소화 시스템이 터질 위험이 있음.
- 현장 작업자 안전 조치 이력:
  1. Supervising Authority 사전 통보 후 VESDA 시스템을 '격리 모드(Isolation Mode)'로 전환 (소화 릴레이 차단 확인).
  2. 검출기 본체와 떨어진 안전 구역에서 400 kPa 압축 공기로 흡입기 및 샘플링 파이프 분진 청소.
  3. 정비 후 필터 교체, 최소 15분 이상 예비 운전 후 배경 스모크 레벨이 0.02% obs/m 이하로 안정화된 것을 확인하고 정상 감시 모드로 복귀.
- 출처: `Field_Troubleshoot_Report_Utility_202610.pdf p.2`

---

## [CASE-09] SmartFDC 드리프트 조기 경보 발생에 따른 SAP PM 워크오더 선제 대응
- 설비: Metal Etch Chamber #2
- 발생 상황:
  전통적인 SPC 관리 한계선은 안 넘었으나, AI 기반 SmartFDC에서 챔버 드리프트 조기 경보(20분 전) 발생.
- 데이터 기반 사전 조치:
  1. SECS/GEM 센서 스트림 분석 결과 RF 파워 제너레이터 열화 패턴 감지.
  2. 웨이퍼 스크랩 발생 전 2단계 수율 예측 모델을 통해 해당 로트 일시 홀드.
  3. 현장 재출동(Truck Rolls)을 줄이기 위해 예비 부품(샤워헤드, 챔버 키트)을 사전에 준비하고 SAP PM 자동 작업 지시서를 승인하여 60분 PM 윈도우 내 신속 교체 완료.
  4. Tool Qual Gate 자동 통과 후 양산 정상 투입.
- 출처: `Field_Troubleshoot_Report_SmartFDC_202610.pdf p.11`

---

## [CASE-10] RTP 급속 열처리 장비 파워 보드 알람 및 시리얼 노이즈 제거
- 설비: AccuThermo AW610 RTP System
- 현상 보고:
  온도 컨트롤러 통신 불량 및 전원 공급 장치 보드 에러(ERR-PWR-SUPPLY-BOARD) 발생하며 램프 파워가 불안정함.
- 엔지니어 조치 내역:
  1. 점검 결과 통신 케이블이 비차폐 일반 케이블로 설치되어 인접 고주파 노이즈 유입 확인 ➔ 전용 차폐 RS-232 케이블(Shielded Cable)로 전면 교체.
  2. 전원부 10,000 AIC 차단기 상태 점검 및 단자 체결 확인.
  3. 제어 소프트웨어 Chapter 5, Section 10의 [ALARM CLEAR] 화면에서 알람 리셋 실행.
  4. 캘리브레이션 테스트 및 1,000℃ 승온 프로파일 테스트 결과 정상 작동 확인.
- 출처: `Field_Troubleshoot_Report_RTP_202609.pdf p.6`
