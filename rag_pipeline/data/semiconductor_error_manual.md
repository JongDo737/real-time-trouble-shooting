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

---

## [SPEC-11] SECS/GEM SmartFDC Multivariate Anomaly Spec
- 문서 식별: MANUAL-FDC-MV-11
- 관련 시스템: SECS/GEM Host 수집 (SVID / ECID / ALID) & SmartFDC 다변량 이상 탐지
- 에러 코드: `ERR-FDC-MV01` (Multivariate Trajectory Break — 단변량 UCL/LCL 이내, 변수 상관 붕괴)
- 탐지 규격:
  * 단변량 SPC가 아니라 챔버 압력, MFC 유량, 온도 컨트롤러 출력의 동적 궤적(Dynamic Trajectory) 군집 이탈을 동시에 본다
  * 압력은 목표값을 유지해도 진공 펌프 전력·펌핑 속도가 기준 궤적 밖으로 벌어지면 배기 라인 부산물 축적으로 판정
  * 경고는 압력 알람보다 먼저 내고, 파티클 역류로 웨이퍼 스크랩이 나기 전에 해당 로트를 홀드한다
- 데이터 항목: 상태 변수(SVID), 장비 상수(ECID), 알람(ALID)을 동일 스텝 시계열로 정렬한 뒤에만 판정
- 출처: `SmartFDC_SECS_GEM_Multivariate_Guide_Sec3_p12.pdf`

---

## [SPEC-12] RF Impedance Match, VSWR & Adaptive Sweep Spec
- 문서 식별: MANUAL-RF-VSWR-12
- 관련 장비: Dry Etch / PECVD RF Generator & Auto Matcher (50 Ω 시스템)
- 에러 코드: `ALARM-VSWR` (Reflected Power / VSWR Limit), `ERR-MUTUAL-CPL` (Multiple RF Mutual Coupling)
- 정합 규격:
  * 전진 전력이 부하에 흡수되지 않고 되돌아오면 반사 전력으로 기록하고 VSWR로 정량화한다
  * 위상(Phase)·크기(Magnitude) 오차가 나면 가변 커패시터와 인덕터를 모터 또는 주파수 튜닝으로 이동한다
  * 어댑티브 스윕(Adaptive Sweep) 수렴 기준: 반사 신호 진동 억제까지 5.0172 ms 이내
  * VSWR 임계 초과 시 자동 전력 제한(Automatic Power Limitation). 다중 RF에서 전력 버스트 이후에도 정합이 안 되면 즉시 셧다운
- 출처: `RF_Auto_Matcher_VSWR_Control_Spec_Sec4_p27.pdf`

---

## [SPEC-13] RF Breakdown EVN Detection & Power Cut Spec
- 문서 식별: MANUAL-RF-BD-13
- 관련 장비: 고진공·고출력 RF 경로 (식각/CVD 챔버, 급전 구간)
- 에러 코드: `ERR-RFBD-EVN` (Multipactor / Corona, Error Vector Noise Trip)
- 탐지 시퀀스:
  * Segment 1: 연속파(CW)로 기준 상태 확인
  * Segment 2: 변조 신호로 배경 노이즈 측정
  * Segment 3: RF 전력을 단계적으로 올리며 방전 감시
- 판정 규격:
  * 정상 EVN 약 -30 dB. 출력단 또는 반사단에서 20 dB 이상 급상승하면 방전(H1)으로 판정. 그 미만은 정상(H0)
  * H1 확정 시 경보, 해당 측정 버퍼 폐기, RF 전력 자동 급감. 마이크로 아크 단계에서 차단
- 출처: `RF_Breakdown_EVN_Detector_Spec_Sec6_p41.pdf`

---

## [SPEC-14] ICP Quartz Window Thickness Loss & OES Life Spec
- 문서 식별: MANUAL-ICP-QZ-14
- 관련 장비: ICP Etch 상단 쿼츠 윈도우(Quartz Window, SiO2) / 알루미나 세라믹 돔
- 에러 코드: `ERR-QZ-LOSS` (Window Thickness Loss — Coupling Drift)
- 마모·안전 규격:
  * 할로겐(F, Cl, Br) 이온 폭격으로 두께가 줄면 안테나-플라즈마 결합 계수가 변하고 중심/가장자리 식각 균일도가 깨진다
  * 임계 두께 미만이면 대기압과 수 mTorr 차압으로 내파(Implosion) 위험이 있으므로 그 전에 교체한다
  * 전기 지표: Auto Matcher 가변 커패시터 모터 스텝이 한 방향으로 장기 편향(Drift)하면 잔여 수명 추론
  * 광학 지표: OES에서 Si·O 라디칼 파장이 기준 피크를 넘으면 쿼츠 부산물 증가로 보고 예방 교체
- 출처: `ICP_Quartz_Window_Life_OES_Spec_Sec5_p33.pdf`

---

## [SPEC-15] AMAT Centura Slit Valve Particle & Response Time Spec
- 문서 식별: MANUAL-SLIT-PRT-15
- 관련 장비: AMAT Centura 5200 Cluster Tool, Transfer-to-Process Slit Valve
- 에러 코드: `ERR-SLIT-DELAY` (Open/Close Response Time Drift)
- 동작 규격:
  * 공압 실린더·캠이 O-ring 도어를 씰면에 밀착. 개폐는 하루 수천 회
  * Standard I/O 보드(0100-02xxx)가 솔레노이드 지령과 리미트 스위치 완료 시각을 비교
  * 정상 완료 시간의 기준값은 0.8초. 이 값이 점진적으로 늘면 공압 누설 또는 가이드 마찰 부하로 판정
- 세정 규격: 일반 클린룸 와이퍼 대신 폼텍(Foamtec) 스크러빙으로 씰 면 부산물과 보푸라기를 제거한 뒤 파티클 카운트
- 출처: `AMAT_Centura_Slit_Valve_Particle_Spec_Sec7_p58.pdf`

---

## [SPEC-16] ESC Helium Cooling Loss & Photoresist Burn Interlock
- 문서 식별: MANUAL-ESC-PR-16
- 관련 장비: Etch / PVD 정전척(ESC) 후면 헬륨 냉각 라인
- 에러 코드: `ERR-PR-BURN` (Photoresist Burn Risk on Helium Cooling Loss)
- 열 한계 규격:
  * 웨이퍼 후면 헬륨은 쿨롱 또는 존슨-라벡 척킹 틈(딤플·헬륨 그루브)으로 열을 전달한다
  * 후면 헬륨 압력이 설정 창(예: 10~20 Torr) 아래로 떨어지면 칠러로의 열교환이 끊긴 것으로 본다
  * 원인 후보: 포커스 링(쿨링 링) 씰 열화, ESC 세라믹 침식, 척킹 전압 강하로 웨이퍼가 들뜸
  * 감광액 열분해·탄화와 선폭(CD) 왜곡을 막기 위해, 누설 유량이 상한을 넘는 순간 1초 이내에 RF를 차단하고 공정을 Abort 한다
- 출처: `ESC_Helium_Photoresist_Interlock_Spec_Sec3_p22.pdf`

---

## [SPEC-17] SEMI S2 Interlock Defeat Key & Auto-Restore Spec
- 문서 식별: MANUAL-SEMI-DEFEAT-17
- 적용 규격: SEMI S2-0703 Section 11.7 (유지보수 중 인터록 우회)
- 에러 코드: `ERR-ILK-KEY` (Defeat Key Not Restored / Unauthorized Bypass)
- 우회 통제:
  * 단일 부품 고장이나 운전 실수가 인명·시설 피해로 이어지지 않도록 하드웨어 인터록을 기본으로 한다
  * Defeat Key와 해제 도구는 시건장치로 보관하고, 자격 있는 책임자(Responsible Person)만 지급한다
  * 우회는 의도적 조작(Intentional Operation)으로만 가능하고, 우회 중에는 출력 제한 로직을 켠다
  * 도어를 닫거나 작업자가 구역을 벗어나면 해제된 인터록은 추가 조작 없이 자동 복원(Automatically Restored)되어야 한다
- 출처: `SEMI_S2_0703_Interlock_Defeat_Key_Sec11_7_p19.pdf`

---

## [SPEC-18] STPA Maintenance Control-State Lock Spec
- 문서 식별: MANUAL-STPA-CTRL-18
- 관련 시스템: 로컬 유지보수 패널 & SECS/GEM E30 Host 명령 경로
- 에러 코드: `ERR-CTRL-STATE` (Local Bypass와 Remote Start 명령 충돌)
- 통제 규격:
  * 인터록 우회 전에 GEM E30 기준 Offline 또는 Online-Local로 강제 전환하고, 소프트웨어가 그 상태를 교차 검증한다
  * 인터록 회선을 하나라도 바이패스하면 작업 허가(Permit to Work) 없으면 공정 시작을 거절한다
  * 우회·임의 배선은 로컬 화면과 EHS 호스트에 동시에 표시한다
  * 양산 복귀는 완료 버튼이 아니라, 커버를 열었을 때 고전압이 실제로 차단됐다는 센서 폐루프가 기록된 뒤에만 허용한다
- 출처: `STPA_Equipment_Control_State_Spec_Sec2_p9.pdf`

---

## [SPEC-19] SEMI S8 HMI Reach & Display Height Spec
- 문서 식별: MANUAL-ERGONOMICS-S8-19
- 적용 규격: SEMI S8 인간공학, EFEM·제어 콘솔 HMI
- 에러 코드: `ERR-HMI-REACH` (Display or Control Outside Reach Envelope)
- 배치 규격 (서 있는 자세):
  * 메인 디스플레이 중심 높이: 1,320 mm ~ 1,470 mm. 화면 상단은 작업자 눈높이보다 높지 않게 한다
  * 다중 모니터 최상단: 1,680 mm (66인치) 이하. 높이 조절 마운트와 틸트 관절 필수
  * 전방 그립 도달(Forward Grip Reach): 장애물 단차에 따라 330 mm ~ 406 mm 이하
  * 터치스크린 하단 조작계: 910 mm (36인치) 이상. 시청 거리 457 mm (18인치) ~ 762 mm (30인치)
  * 한국 남성 95백분위 눈높이는 서구권 기준보다 약 32 mm 낮다. 고정 높이 대신 교대마다 조절 가능한 HMI를 쓴다
- 출처: `SEMI_S8_HMI_Reach_Envelope_Sec4_p16.pdf`

---

## [SPEC-20] Unified Predictive Maintenance Fusion Architecture
- 문서 식별: MANUAL-UPDM-ARCH-20
- 관련 시스템: 엣지 DAQ, 도메인 SmartFDC, SEMI S2/S8 Safe-HMI
- 에러 코드: `ERR-UPDM-FUSE` (Cross-Domain Misalignment Signature)
- 융합 판정:
  * 엣지 계층: 슬릿 밸브 닫힘 지연과 ESC 후면 헬륨 압력 변동을 동일 타임스탬프(마이크로초)로 묶는다
  * 도메인 계층: 밸브 지연, 헬륨 누설, RF Auto Matcher 튜닝 시간 증가가 같이 나오면 개별 센서가 한계치 전이라도 웨이퍼 안착 불량·척킹 이상 징후로 보고 공정을 미리 멈춘다
  * 안전 계층: 이상 확정 시 SEMI S2에 따라 가스·고전압을 끊고 Safe Standby로 전환한다. 도착한 작업자 키에 맞춰 SEMI S8 높이로 HMI를 맞추고, 챔버 온도·잔존 유해가스·해제된 인터록 위치를 표시한 뒤에만 정비 진입을 허용한다
- 출처: `Unified_Predictive_Maintenance_Architecture_Sec8_p44.pdf`

---

## [SPEC-21] Turbo Molecular Pump Bearing Vibration Spec
- 문서 식별: MANUAL-VAC-TMP-21
- 관련 장비: 프로세스 챔버 고진공 터보 분자 펌프 (Turbo Molecular Pump)
- 에러 코드: `ERR-TMP-VIB` (Bearing Vibration Limit Exceeded)
- 운전 규격:
  * 정상 회전 진동: 0.5 mm/s RMS 미만. 경고 1.0 mm/s, 트립 2.0 mm/s
  * 정격 회전수 도달 시간: 기동 후 8분 이내. 12분을 넘기면 베어링 또는 로터 밸런스 이상
  * 펌프 바디 온도 상한: 냉각수 정상 유량에서 65°C. 70°C 초과 시 런 금지
  * 포어라인 압력은 러핑 완료 후 0.5 Torr 미만에서만 터보 기동
- 점검: 자기 부상 전류가 정격의 30%를 넘으면 로터 접촉 전 단계로 보고 베어링 카트리지를 교체한다
- 출처: `Turbo_Pump_Vibration_Limit_Spec_Sec4_p21.pdf`

---

## [SPEC-22] Process Cooling Water Flow & Temperature Spec
- 문서 식별: MANUAL-UTIL-PCW-22
- 관련 장비: RF 제너레이터, 터보 펌프, ESC 칠러 공통 PCW 매니폴드
- 에러 코드: `ERR-PCW-FLOW` (Process Cooling Water Low Flow)
- 공급 규격:
  * 공급 온도 18~22°C, 설비 입구·출구 차이(ΔT) 5°C 이하가 정상. ΔT 8°C 초과는 유로 막힘
  * 분기 유량 스위치 트립: 설정 유량의 80% 미만이 10초 지속
  * 공급 압력 3.0~4.5 barg. 2.5 barg 미만이면 RF와 히터 출력을 내린다
  * 수질: 저항률 1 MΩ·cm 이상, 입자 5 μm 미만. 도전성 냉각수는 전극 누설 전류를 만든다
- 출처: `Fab_PCW_Supply_Spec_Sec2_p11.pdf`

---

## [SPEC-23] Capacitance Manometer Zero Drift Spec
- 문서 식별: MANUAL-VAC-CM-23
- 관련 장비: 프로세스 챔버 가열형 정전용량 진공계 (100 mTorr / 1 Torr Baratron)
- 에러 코드: `ERR-CM-ZERO` (Manometer Zero Drift)
- 교정 규격:
  * 게이지 히터 설정 100°C 또는 45°C를 레시피와 같게 유지. 온도가 다르면 영점을 다시 잡는다
  * 영점 조건: 챔버 1×10^-5 Torr 이하에서 30분 안정 후 영점. 허용 오프셋은 풀 스케일의 ±0.05%
  * 풀 스케일 0.5%를 넘는 영점 이동은 다이어프램 오염으로 보고 게이지를 교체한다
  * 영점 직후 30분 안에 공정 가스를 넣지 않는다. 열 재평형 전에 읽은 압력은 폐기한다
- 출처: `Capacitance_Manometer_Zero_Spec_Sec3_p17.pdf`

---

## [SPEC-24] APC Throttle Valve Pressure Control Spec
- 문서 식별: MANUAL-VAC-APC-24
- 관련 장비: 챔버 압력 제어 자동 압력 조절 밸브 (APC Throttle Valve)
- 에러 코드: `ERR-APC-HUNT` (Throttle Position Oscillation)
- 제어 규격:
  * 압력 안정도: 설정값 대비 ±2% 이내, 5초 창. 밸브 개도 진동 폭 5%p를 넘으면 헌팅으로 판정
  * 개도 정상 구간: 15~85%. 10% 미만 또는 90% 초과로 고정되면 펌프 능력 또는 가스 부하 불일치
  * 스텝 변경 후 압력 정착: 3초 이내. 게인(P)을 올리면 오버슈트가 늘므로 I 시간을 먼저 늘린다
  * 밸브 플레이트에 막이 앉으면 같은 개도에서 컨덕턴스가 줄어 압력 설정값을 못 맞춘다
- 출처: `APC_Throttle_Tuning_Spec_Sec5_p29.pdf`

---

## [SPEC-25] OES Endpoint Detection Window Spec
- 문서 식별: MANUAL-ETCH-EPD-25
- 관련 장비: 식각 챔버 광학 발광 분석기 (OES Endpoint Detector)
- 에러 코드: `ERR-EPD-MISS` (Endpoint Wavelength Not Detected)
- 판정 규격:
  * 주 파장 예: 산화막 식각 CO 483 nm, 질화막 CN 387 nm. 보조 파장과 강도 비가 기준의 70% 미만이면 창 오염
  * 뷰포트 석영 투과율이 초기 대비 80% 미만이면 엔드포인트 창을 교체한다. 챔버 벽 쿼츠 윈도우 마모 기준과는 별도다
  * 시간 엔드포인트 백업: 광학 신호가 최대 식각 시간의 110%까지 안 나오면 과식각 전에 스텝을 멈춘다
  * 광섬유 굽힘 반경 50 mm 미만은 금지. 기준 램프 강도가 10% 이상 떨어지면 분광기 교정을 다시 한다
- 출처: `OES_Endpoint_Window_Spec_Sec6_p36.pdf`

---

## [SPEC-26] Load Lock Pumpdown Time Spec
- 문서 식별: MANUAL-VAC-LL-26
- 관련 장비: 300mm 로드락, 러핑 펌프와 슬로우 펌핑 밸브
- 에러 코드: `ERR-LL-SLOW` (Load Lock Pumpdown Timeout)
- 배기 규격:
  * 대기압에서 1 Torr까지 슬로우 펌핑 20초, 이후 러핑으로 50 mTorr까지 총 90초 이내
  * 120초를 넘기면 도어 O-ring, 러핑 밸브 시트, 펌프 오일 역류를 순서대로 본다
  * 벤트는 N2로 대기압 −10 ~ +20 Torr 안에서 열고, 오버벤트 시 웨이퍼 날림으로 인터록
  * 슬로우 펌핑을 건너뛰면 파티클이 떠오르므로 레시피에서 그 스텝을 지우지 않는다
- 출처: `Loadlock_Pumpdown_Spec_Sec2_p14.pdf`

---

## [SPEC-27] CVD Showerhead Clogging & Uniformity Spec
- 문서 식별: MANUAL-CVD-SH-27
- 관련 장비: AMAT Producer CVD 샤워헤드 및 페이스 플레이트
- 에러 코드: `ERR-SH-CLOG` (Showerhead Hole Restriction)
- 증착 규격:
  * 막 균일도 1σ 1.5% 이내. 2.5%를 넘고 가장자리가 두꺼우면 중심 홀 막힘으로 의심
  * 샤워헤드 차압: 같은 유량에서 기준 대비 +15%면 홀 제한, −10%면 홀 확대 또는 누설
  * 페이스 플레이트 온도 편차 존 간 3°C 초과 시 증착 속도 맵이 기울어진다
  * 세정: NF3 리모트 플라즈마 시즌 후 더미 웨이퍼 5매. 차압이 안 돌아오면 플레이트 탈거 습식 세정
- 출처: `AMAT_Producer_Showerhead_Uniformity_Spec_Sec4_p31.pdf`

---

## [SPEC-28] ALD Precursor Bubbler Temperature Spec
- 문서 식별: MANUAL-ALD-BUB-28
- 관련 장비: ALD 전구체 버블러, 히팅 재킷, 캐리어 가스 라인
- 에러 코드: `ERR-BUBBLER` (Precursor Temperature Out of Window)
- 공급 규격:
  * 버블러 온도는 증기압 곡선의 설정값 ±0.3°C. ±1.0°C를 넘으면 도즈가 레시피 허용을 벗어난다
  * 버블러에서 챔버까지 라인 온도는 버블러보다 10~20°C 높게 유지해 응축을 막는다
  * 캐리어 유량은 MFC 풀 스케일이 아니라 버블러 출구 압력 게이지가 설정 ±2%인 때로 확인한다
  * 앰플 잔량 10% 미만에서는 액면이 흔들려 도즈가 튀므로 교체 창으로 넘긴다
- 출처: `ALD_Bubbler_Temperature_Spec_Sec3_p19.pdf`

---

## [SPEC-29] ESC Dechuck Voltage Decay Spec
- 문서 식별: MANUAL-ESC-DECHUCK-29
- 관련 장비: 식각 ESC 디척 전원 및 리프트 핀 인터록
- 에러 코드: `ERR-DECHUCK` (Wafer Stick After Dechuck)
- 해제 규격:
  * 디척 전압은 척킹 전압의 역극성으로 풀 스케일의 20~40%를 2초 인가한 뒤 0 V로 방전한다
  * 잔류 전압이 ±50 V 안으로 들어오기 전에 리프트 핀을 올리지 않는다. 핀 선행 상승은 웨이퍼 파손
  * 플라즈마 오프 후 전하 감쇠 대기 3초. 헬륨 후면 압력은 핀 상승 전에 0.5 Torr 미만으로 뺀다
  * 같은 레시피에서 스틱이 3회 연속이면 척 표면 폴리머를 벗기고 디척 레시피를 다시 맞춘다
- 출처: `ESC_Dechuck_Sequence_Spec_Sec5_p27.pdf`

---

## [SPEC-30] Lift Pin Height & Wafer Clearance Spec
- 문서 식별: MANUAL-CHAMBER-PIN-30
- 관련 장비: LAM 식각 챔버 리프트 핀 3점과 블레이드 진입 높이
- 에러 코드: `ERR-LIFT-PIN` (Pin Height Mismatch)
- 높이 규격:
  * 핀 상단 높이 편차 핀 간 ±0.1 mm 이내. 0.3 mm를 넘으면 웨이퍼가 기울어 핀 자국이 난다
  * 블레이드 진입 간격: 웨이퍼 하면과 핀 끝 사이 1.5~2.5 mm. 1.0 mm 미만은 긁힘, 3.0 mm 초과는 안착 충격
  * 핀 상승 완료 센서와 엔코더 높이가 0.2 mm 이상 어긋나면 이송을 멈춘다
  * 핀 벨로우즈 리크는 헬륨 리크 체크와 분리해, 핀을 올린 상태와 내린 상태를 각각 측정한다
- 출처: `LAM_Lift_Pin_Height_Spec_Sec6_p24.pdf`
