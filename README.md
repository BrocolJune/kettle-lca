# BC1 1 L 전기주전자 생산 단계 LCA

**독립 실행 결과:** 포장된 주전자 1대의 공장 출하 전 GWP100은 **5.0865 kg CO₂-eq**이다. 이 값의 **47.8%가 명시적 가정**에 의존하고 공급자 교환 641건이 미연결 상태이므로 검증된 제품 탄소발자국이 아닌 **스크리닝 추정**이다. 전체 표와 그림은 [HTML 보고서](results/report.html)에 있다.

> 범위: 원자재 공급 → 부품 생산 → 조립 → 포장 → 공장 출하. 제품 사용 중 전력 소비와 사용 후 폐기는 제외한다. 제조 전력과 제조 스크랩은 생산 단계에 포함한다.

## 1. 연구 식별과 목적

| 항목 | 내용 |
|---|---|
| 제목 | 대표 BC1 1 L 플라스틱 전기주전자의 공장 출하 전 LCA |
| 공개 별칭·저장소 | BrocolJune · <https://github.com/BrocolJune/kettle-lca> |
| 실행 ID·날짜 | `bc1-uslci-independent-2026-10-08` · 2026-10-08 |
| 실행 구분 | 독립 실행; `independent-run` 태그로 결과 보존 |
| 목표·비교 | 재료 및 제조의 GWP100 주요 기여와 데이터 공백 파악. 현재는 USLCI 단일 기준 모델만 계산했으며 TianGong 수치 비교는 수행하지 않음 |

최종 40자리 커밋 SHA는 커밋·푸시 후 제출 양식에 기입한다. README에는 자기 자신의 미래 커밋 해시를 넣지 않는다. 실명·이메일·제출 코드는 공개 파일에 없다.

## 2. 제품, 선언 단위와 시스템 경계

선언 단위: **제조·포장된 대표 BC1 1 L 전기주전자 1대, 공장 출하 시점**. BC1은 실존 상표 제품이 아니다. [BOM](data/source/kettle-bom.csv)은 과제 사이트에서 2026-10-08 가져왔고 EU Electric Kettles preparatory study (2020), Task 4 Tables 4-3/4-4/4-8에 근거한다. 본체 **723.0 g** + 포장 **137.8 g** = **860.8 g**을 검산했다.

포함: 12개 BOM 재료 공급, 부품 가공, 조립 전력, 포장, 공급자→조립 공장 운송 가정. 제외: 고객 배송, 주전자 사용 전력, 수리·세척, 사용 후 재활용·매립·소각. 제조 과정에서 생긴 스크랩의 처리 부담은 생산 단계다. BOM 질량에 임의 절단값은 적용하지 않았다. 배경 공정 자체의 절단 기준은 일부 unknown이다. 실제 제조 지역과 생산 기준연도는 **unknown**이고 미국·북미 공정을 지역 대리값으로 사용했다. BOM 기반 연도 2020과 USLCI 릴리스 2026의 시점 차이도 한계다. 경계 도식은 [보고서](results/report.html)에 있다.

## 3. 전경 인벤토리와 정량 가정

각 재료의 완성 질량·구매량은 [매핑 표](data/mapping/mapping-decisions.csv), 전체 매개변수는 [모델 입력](data/model.json)에 있다. 상태 `sourced`는 BOM/DB 기록, `estimated`는 공정 유추, `assumed`는 실측 근거가 없는 모델 선택이다.

| 항목 | 값 | 상태·근거 |
|---|---:|---|
| 본체 및 포장 완성 질량 | 723.0 g / 137.8 g | sourced, BOM |
| 일반 재료 손실 | 5% | assumed; 구매량=완성 질량/0.95 |
| PP 사출 수지 투입 | 1.034 kg/kg 부품 | sourced, USLCI 사출 공정; 일반 손실 미중복 |
| 기타 열가소성 수지 가공 전력 | 1.79 kWh/kg | estimated, PP 사출 공정의 6.444 MJ/kg 대리 적용 |
| 실리콘·금속·골판지·필름 가공 전력 | 1.79 / 0.50 / 0.30 / 0.50 kWh/kg | assumed |
| 조립 전력 | 0.20 kWh/대 | assumed, 공장 실측 없음 |
| 공급자→조립 공장 거리 | 500 km | assumed, 원산지 미상 |
| 제조 스크랩 처리·가격 | 수율 가정; 전경 구매 가격 not applicable | 재활용 크레딧 없음, 별도 가격 사용 없음 |

단위 변환은 g/1000=kg, 1 kWh=3.6 MJ, 1 t·km=1000 kg·km이다. PP 사출 공정에는 수지·성형 전력·공정 손실이 이미 포함되므로 PP 수지나 전력을 다시 더하지 않았다. 다른 수지에는 원료 공정과 전경 가공 전력을 분리했다. 실제 스크랩 처리 경로는 unknown이다.

## 4. 배경 데이터와 매핑 결정

기준 데이터는 [USLCI 1.2026-09.0](https://github.com/FLCAC-admin/uslci-content/blob/dev/docs/release_info/release-downloads.md)이다. GitHub `.zolca` 원본과 같은 릴리스의 Federal LCA Commons JSON-LD를 로컬에 보관했고 계산은 JSON-LD를 읽는다. 원본 URL·릴리스·SHA256·획득일은 [자료 명세](data/manifest.json), 항목별 검색어·후보·선택/기각 이유·UUID·버전·지리·유효연도·기준 흐름/단위는 [매핑 표](data/mapping/mapping-decisions.csv)에 있다. [다운로드 절차](docs/data-access.md)도 제공한다.

스테인리스 304 코일, PP 사출, PVC/ABS/LDPE 수지, 골판지 평균 생산, 미국 전력 브리지와 트럭 공정을 선택했다. **황동, 구리, 등급 미상 나일론, POM, PC, 실리콘**은 적합한 독립 USLCI 공정이 없거나 USEEIO 통화 브리지가 미연결이라 각각 **4, 4, 6, 4, 5, 6 kg CO₂-eq/kg을 가정**했다. 이 값은 문헌 측정치가 아니다.

2026년 9월 USLCI에는 내장 전력 라이브러리가 없어 외부 전력 공급자 연결이 필요하다. 이 모델은 미연결 전력을 **0.4 kg CO₂-eq/kWh**로 가정했다. 다른 공급자 641건의 사유·대체계수·기여는 [상세 CSV](results/unresolved-providers.csv)에 있다. 배경의 USD 단위 미연결 교환 25건에는 0.5 kg CO₂-eq/USD를 가정했다. 통화는 USD이나 업종, 가격 연도 및 구매자/기초가격 기준은 **unknown**이다. 교환별 수량은 상세 CSV, 이 가정의 총량 기여는 약 0.009 kg CO₂-eq/대다. 통화 브리지와 직접 물질 공정을 동등하다고 간주하지 않았다.

## 5. 계산 및 영향평가 방법

[계산 코드](src/lca.py)는 공정 기준 흐름으로 정규화한 직접 배출과 공급자 계수를 만든다. `A s = f`의 공정별 계수 형태로 **`(I − M)x = d + q`**를 SciPy 희소 행렬로 푼다. M은 상류 투입, d는 직접 특성화 배출, q는 미연결 공급자에 둔 명시적 가정, x는 기준 흐름 단위의 총계수다. 전경 수요와 x의 내적으로 총량을 계산한다. 공급자 흐름 UUID와 단위가 맞을 때만 연결한다. 누락 흐름을 0으로 취급하지 않는다. USLCI의 누적 `LCI_RESULT` 공정은 재확장하지 않는다.

특성화는 [FLCAC LCIAformatter의 IPCC AR6 GWP100 표](https://github.com/FLCAC-admin/LCIAformatter/blob/master/lciafmt/data/IPCC_GWP_values.csv), 소스 커밋 `48d19af11965994378e9febe0cca2d5822a0776d`, **100년**, kg CO₂-eq/kg 기체다. `AR6`·`GWP100` 행만 사용한다. 공기 배출 112개 흐름 UUID를 이름/CAS로, 생물기원 CH₄ 3개는 CH₄=27.9로 매칭했다. 생물기원 CO₂ 3개는 0으로 처리했다. 집계형 CFC/HCFC/HFC/PFC 등은 미특성화다. 이 매칭은 공식 openLCA LCIA 실행과 동일하다고 검증되지 않았다.

15개 다산출 공정은 추가 배분을 재현하지 못해 기준 산출물에 전체 잔여 부담을 귀속했다. 재활용 크레딧은 없다. 배경 운송·연료 부담은 공급망 안에 있고 전경 500 km는 공급자→조립 공장 구간만 뜻한다. 중복 가능성은 남는다.

## 6. 재현 방법

Windows ARM64, Python 3.13.0, NumPy 2.1.3, SciPy 1.15.3에서 실행했다. [requirements.txt](requirements.txt)에 계산 의존성을 고정했다. 이 호스트에서는 conda-forge 패키지를 가상환경에 노출했다. 다른 환경에서는 가상환경에서 `python -m pip install -r requirements.txt`를 쓸 수 있다.

```powershell
Set-Location 'C:\path\to\kettle-lca'
python -m venv --system-site-packages .venv
# docs/data-access.md에 따라 data/raw/에 원본 파일 확보
.\.venv\Scripts\python.exe -m src.lca
.\.venv\Scripts\python.exe -m src.render_report
start .\results\report.html
```

필요 입력 파일은 `data/raw/uslci_commons_export.zip`, `data/raw/IPCC_GWP_values.csv`, `data/raw/uslci_v1.2026-09.0_olca2_7_1.zolca`다. 마지막 `.zolca`는 출처 SHA 기록용이다. 사이트 직접 다운로드 또는 `.zolca`의 openLCA JSON-LD 내보내기 방법은 [자료 안내](docs/data-access.md)에 있다. 계산에는 API 키가 필요 없다. 원본은 Git에서 제외한다. 결과는 `results/run.json`, `contributions.csv`, `unresolved-providers.csv`, `report.html`이다. 입력·매핑·코드·결과·결정 기록 위치는 위 링크에서 확인할 수 있다. 난수 시드는 `20261008`이다.

## 7. 결과·검산·해석

상태: **계산된 스크리닝 추정, 공급자 폐쇄 실패**. 기준 GWP100 **5.0865 kg CO₂-eq/포장된 주전자 1대**. 상위 세 항목은 스테인리스 **1.7651**, PP 사출 **1.5232**, 골판지 **0.4733 kg CO₂-eq/대**다. 전체 기여도는 [CSV](results/contributions.csv)·[JSON](results/run.json)·[HTML](results/report.html)에 있다. TianGong 비교 및 대체 시나리오 결과는 **not calculated**다.

| 검산 | 결과 |
|---|---|
| 질량 | 723.0 + 137.8 = 860.8 g, 통과 |
| 단위 | 명시적으로 변환; 공급자 단위 불일치 102건은 미연결 처리 |
| 공급자 연결 | 383개 공정 도달, 641개 교환 미연결·가정 대체, 폐쇄 실패 |
| 기여도 합 | 단계 합과 총량 차이 0.0 kg CO₂-eq |
| 이중계산 | PP 수지·전력은 별도 청구하지 않음; 다른 배경 중복 가능성 미해결 |
| 미특성화 | 공기 배출 이름 620개는 GWP100 계수가 없거나 생물기원 CO₂ 정책 대상; 일부 집계형 온실가스 포함 |

직접 USLCI 인벤토리 특성화는 **2.6566**, 나머지 가정 부분은 **2.4299 kg CO₂-eq/대**다. 제조지, 합금·수지 등급, 수율, 실제 폐기·전력·운송, 다산출 배분과 집계형 온실가스 누락이 한계다. 타 제품 우월성이나 인증용 탄소발자국을 주장할 수 없다. 제품 사용과 사용 후 폐기는 **not calculated**다.

## 8. 불확실성과 민감도

가정 계수 분류마다 독립 삼각분포 배수(최소 0.5, 최빈 1, 최대 1.5)를 적용해 10,000회 모의했다. 시드 `20261008`. 조건부 평균 **5.0840**, 중앙값 **5.0809**, P05–P95 **4.7202–5.4522 kg CO₂-eq/대**다. 전·후반 표본 분위수 차이는 [실행 JSON](results/run.json)에 있다. 분포 범위는 측정 오차가 아닌 분석 가정이다. 계수 간 실제 상관성은 unknown이라 독립으로 두었다. 수율, 지역, 공급자 구조, 배분, 미특성화 흐름, AI 반복 실행 변동은 이 구간에 포함되지 않으며 마지막 항목은 **not calculated**다.

## 9. Codex와 사람의 결정

2026-10-08 실행. 작업 환경은 **GPT-6 기반 Codex**로 표시되며 정확한 변형/빌드와 일부 설정은 **unknown**이다. 학생은 USLCI 대체, 공식 파일 로컬 사용, 생산 단계 경계와 HTML 보고서를 결정했다. Codex는 후보 검색, 매핑, 모델 가정, 계산 및 보고서를 작성했다. 여섯 미대응 재료의 가정값은 학생의 실측치가 아닌 Codex의 선택이다. 후보 기각·분류 오류 수정·주요 결정은 [공개 결정 기록](docs/decisions.md)에 있다. BOM 질량, 기여도 합과 원본 SHA256은 점검했다. 학생의 데이터·가정별 별도 검토 여부는 **unknown**이다. 비공개 메시지·계정·인증 정보는 공개하지 않는다.

## 10. 독립 및 수정 실행

현재는 **독립 실행 결과**다. 이 버전은 `independent-run` 태그로 보존하고 전체 40자리 SHA를 제출 양식에 사용한다. 수업 제출 양식은 저장소 안에서 작성하지 않았다. 동료 결과를 본 뒤의 한 가지 선택 변경, 예측 효과, 이전/수정 값, 절대·백분율 차이와 수정 커밋은 **not applicable — 수정 실행 전**이다. 독립 실행 결과는 수정 때 덮어쓰지 않는다.
