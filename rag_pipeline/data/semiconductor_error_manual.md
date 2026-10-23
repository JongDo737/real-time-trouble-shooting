# SEMICONDUCTOR EQUIPMENT ERROR CODE & SPECIFICATION MANUAL
문서 번호: SOP-SEMI-SPEC-2026-V1
적용 대상: 식각(Etch), 증착(CVD/ALD), 노광/이송(Track/WHR), 열처리(RTP) 전 공정

---

## [SPEC-01] RF Power Generator & Auto Matcher Error Code
- 문서 식별: MANUAL-RF-ETCH-01
- 관련 장비: 13.56 MHz RF Generator (AE Cesar 1312 / Seren MC2 Auto Matcher)
- 에러 코드: `ALARM-402` (Reflected Power Limit Exceeded), `ERR-MATCH-TUNE`
- 규격 임계치:
  * 정상 반사파(Reflected Power): 순방향(Forward Power) 대비 5% 미만 (<5%)
  * 경고 임계치: 순방향 대비 10% 초과 (>10%)
  * 설비 트립(Interlock Trip): 순방향 대비 15% 초과 (>15%)
- 안전 규격: SEMI S2 Section 11 / SEMI S8 준수. 점검 전 메인 AC 주전원 분리 및 10,000 AIC 차단기 OFF 필수.
- 하드웨어 점검 기준:
  * 가변 커패시터(Variable Capacitor) 플레이트 아킹(Arcing) 흔적 및 모터 양단(MIN/MAX) 이동 점검
  * 모든 은도금(Silver-plated) RF 단자는 규정 토크(Torque: 4.5 Nm)로 체결되어야 함
  * 급전선 반사 손실(Return Loss) 정상 기준: -14 dB 이하 (10 dB는 반사파 10% 유발)
- 출처: `AE_Cesar_RF_Manual_Ch6_Troubleshooting_p168.pdf`

---

## [SPEC-02] ICP-RIE Plasma Chamber Ignition Standard
- 문서 식별: MANUAL-ICP-IGN-02
- 관련 장비: 고밀도 유도결합 플라즈마 식각기 (ICP-RIE System)
- 관련 상태: `NO-ALARM-IGNITION-FAIL` (에러코드 없이 플라즈마 점화 불능)
- 공정 물리 파라미터 기준:
  * 정상 점화 압력 윈도우(Ignition Window): 20 ~ 200 mTorr
  * 정상 반사파 한계: 점화 시점 반사파 50% 초과 시 임피던스 극단 불일치로 판정
  * 석영 유전체 윈도우(Quartz Dielectric Window) 식각 마모 한계: 0.5 mm 초과 시 즉시 교체
- 점검 표준 절차: 가스 유량(MFC) ➔ 챔버 압력(20~200mTorr) ➔ RF Forward 전력 ➔ 반사파 50% 이하 ➔ 윈도우 마모 확인 ➔ Ar 가스 점화 테스트
- 출처: `RIE_ICP_Maintenance_Guide_Sec5.3_p89.pdf`

---

## [SPEC-03] Mass Flow Controller (MFC) Flow & Pressure Specification
- 문서 식별: MANUAL-GAS-MFC-03
- 관련 장비: Brooks Instrument Series GF40 / Azbil 디지털 질량 유량 제어기
- 에러 코드: `AL40` (Excessive Flow Rate - 유량 표시 범위 초과), `AL82` (Sensor Error 2)
- 동작 및 조정 규격:
  * 인렛 압력 불안정 시 오실레이션(헌팅) 방지를 위해 인렛 압력을 2 psig 단위로 상하향 조정 (2 psig increments)
  * 영점 보정(Zero Adjustment): 밸브 양단 압력 평형 후 도면 Figure 2-2의 Zero 버튼을 최소 5초간(min 5 seconds) 지속 압입
  * Auto Shut-Off: 셋포인트가 풀 스케일(Full Scale)의 1.5% 미만 도달 시 밸브 자동 차단
- 안전 경고: 독성/반응성 가스 라인은 정비 전 반드시 펌프다운과 N2 퍼지를 병행해야 함
- 출처: `Brooks_GF40_Operation_Manual_Sec2_17_p23.pdf`

---

## [SPEC-04] SEMI S2 Safety Interlock Defeat & EMO Protocol
- 문서 식별: MANUAL-SEMI-SAFE-04
- 적용 규격: SEMI S2-0818 Environmental, Health, and Safety Guideline
- 안전 인터록 우회 규정 (Section 11.7):
  * 유지보수(PM) 모드에서 인터록 우회는 반드시 '도구(Tool)'를 사용하는 의도적 조작으로만 가능 (임의 점퍼선 금지)
  * 유지보수 작업 완료 또는 인클로저 도어 닫힘 시 인터록은 반드시 '자동 복원(Automatically Restored)'되어야 함
- EMO (Emergency Off) 전원 규격 (Section 12.2 & 12.3):
  * EMO 버튼 작동 시 24V 제어 회로를 제외한 모든 위험 전압 및 240 VA 초과 전원 즉시 차단
  * EMO 스위치를 물리적으로 복구하더라도 전원이 자동 재인가되어서는 안 되며, 반드시 '수동 리셋(Manual Resetting)' 절차 필수
- 출처: `SEMI_S2_0818_Safety_Standard_Sec11_p45.pdf`

---

## [SPEC-05] Electrostatic Chuck (ESC) & Powered Electrode Spec
- 문서 식별: MANUAL-CHAMBER-ESC-05
- 관련 장비: 300mm ICP Etch Chamber ESC & Lower Powered Electrode
- 에러 코드: `HE-LEAK-HIGH` (Backside Helium Leak-up-rate Limit Exceeded)
- 공정 한계치:
  * DC 셀프 바이어스(DC Self-Bias): 기준 전압 대비 편차 ±10% 이내 정상 (±15% 초과 시 Warning)
  * 실리콘 전극(Silicon Electrode) 교체 기준: 두께 손실(Thickness Loss)이 초기 대비 10% 초과 시 또는 표면 Pitting 발생 시 교체
- 서비스 진단 루틴: 내장 [Helium Leak Check] 소프트웨어 자동 진단 절차 준수
- 출처: `ICP_Service_Manual_V2.4_Sec3_2_5_p67.pdf`

---

## [SPEC-06] Wafer Handling Robot (WHR) Positioning & Homing Spec
- 문서 식별: MANUAL-ROBOT-WHR-06
- 관련 장비: Logosol 4-Link SCARA Wafer Handling Robot / Brooks MagnaTran 7.1
- 에러 코드: `ERR-WHR-OUT-OF-POCKET` (웨이퍼 안착 위치 이탈 에러)
- 4대 광학 센서 엣지 판정 조건:
  * Condition 1: 최소 슬롯 스텝 미만 (웨이퍼가 블레이드 뒤로 너무 밀림, Too far back)
  * Condition 2: 최소 슬롯 ~ 포켓 이탈 스텝 사이 (정상 포켓 안착, In the pocket, 위치 정밀도 ±0.1mm)
  * Condition 3: 포켓 이탈이나 보정 가능 범위 (Too far forward ➔ 엘리베이터 임시 적재 후 자동 Centering 보정)
  * Condition 4: 자동 보정 불가 범위 이탈 (Out of pocket and not correctable ➔ 즉시 인터록 정지)
- 엔코더 호밍 절차: 증분형 위치 엔코더(Incremental Encoders)는 Section 5.9.1 원점 복귀 후 Section 5.9.2 홈 오프셋 설정
- 출처: `Logosol_Robot_Application_Manual_Doc710010010_Sec5_9_p46.pdf`

---

## [SPEC-07] Vacuum Slit Valve & Chamber Seal Parts Catalog
- 문서 식별: MANUAL-VAC-VALVE-07
- 관련 장비: 300mm Transfer-to-Process Chamber Vacuum Isolation
- 규격 절차: Section 7.5.1 Vacuum System Leak Check
- 공인 정품 파트 넘버 (Part Numbers):
  * Slit Valve Actuator Seal (5000 ZA): `AMAT 0190-09539`
  * Slit Valve Door Liner: `P/N 0021-09718`
  * Chamber Liner CT+ w/ Leak Port (300mm): `AMAT 0040-87219`
  * Leak Check T-Valve S-Plate: `AMAT 0242-38184`
- 주의 사항: 서비스 모드(Service Mode) 진입 시 슬릿 밸브 및 웨이퍼 클램프 인터록이 무시되므로 협착 위험 주의
- 출처: `AMAT_Centura_Slit_Valve_Maintenance_Manual_Sec7_5_p112.pdf`

---

## [SPEC-08] Sub-Fab Fire Protection VESDA Isolation Standard
- 문서 식별: MANUAL-UTIL-VESDA-08
- 관련 장비: Xtralis VESDA LaserPLUS / VESDA VSC Aspirating Smoke Detector
- SEMI 연동 규격: SEMI S2 Section 14.4.3 화재 감지 시 설비 전원/케미컬 인터록 강제 셧다운 연동
- 정비 사전 격리(Isolation) 기준:
  * Xtralis VSC 소프트웨어에서 Significant Smoke Change 설정값 확인 (공장 초기값: 0.02% obs/m)
  * 정비 모드 진입 시 모니터링 패널 소화 릴레이 차단(Fault 상태 전송되나 소화가스 트립 방지)
  * 흡입기 청소: 검출기 본체와 분리된 장소에서 400 kPa 압축 공기로 청소
  * 복구 기준: 필터 교체 후 최소 15분 이상 가동 안정화 ➔ Raw Airflow 정규화 ➔ 감도 0.02% obs/m 복귀
- 출처: `Xtralis_VESDA_Maintenance_Guide_Sec2_4_p14.pdf`

---

## [SPEC-09] SmartFDC Telemetry & SAP PM Work Order Spec
- 문서 식별: MANUAL-AI-FDC-09
- 관련 시스템: SECS/GEM 300 Telemetry Streaming & SAP PM / IBM Maximo EAM
- 조기 경보 알고리즘 규격:
  * SECS/GEM 센서 데이터 기반 SPC 한계선 돌파 20 ~ 40분 전 조기 경보 발령
  * 2단계 수율 예측 모델 (R² ≈ 0.5): 6개 핵심 공정 스텝 데이터로 이상 로트 수 시간 내 사전 홀드
  * 연동 소모품 사전 예측: 챔버 키트, 샤워헤드, RF 제너레이터 출고 티켓 발행으로 재출동(Truck Rolls) 35% 절감
- 양방향(Bi-directional) 워크플로: SAP PM 작업 지시서 생성 ➔ 모바일 코파일럿 작업 완료 ➔ Tool Qualification Gate 자동 승인
- 출처: `Semiconductor_Fab_SmartFDC_Integration_Guide_p34.pdf`

---

## [SPEC-10] RTP Temperature Controller & Power Board Spec
- 문서 식별: MANUAL-RTP-THERMAL-10
- 관련 장비: AccuThermo AW410/AW610 Rapid Thermal Processing & Sekienko 2000F
- 에러 코드: `ERR-PWR-SUPPLY-BOARD`, `TEMP-COMM-FAIL`
- 전장 및 통신 안전 규격:
  * RS-232 시리얼 통신: 전자기 노이즈 방지를 위해 반드시 차폐 케이블(Shielded Cables Only) 사용 의무
  * 전원 보호: 메인 전원 인입부에 최소 10,000 AIC (10,000A) 과전류 차단기 장착 필수
  * SEMI S8 인체공학 규격: 디스플레이 중심선은 바닥으로부터 0.0 cm ~ 162.6 cm(64인치) 사이에 설치
- 알람 클리어 절차: 제어 소프트웨어 Chapter 5, Section 10의 [ALARM CLEAR] 화면에서 해당 알람 리셋
- 출처: `AccuThermo_AW610_RTP_System_Manual_Sec2_5_p18.pdf`
