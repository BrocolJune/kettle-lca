# 원본 데이터 확보와 출처

계산 코드는 `data/raw/uslci_commons_export.zip`과 `data/raw/IPCC_GWP_values.csv`를 읽는다. 두 파일은 Git에 포함되지 않는다. `data/manifest.json`에 정확한 SHA256과 URL이 있다. 사용한 JSON-LD 내보내기는 USLCI 1.2026-09.0으로 선택된 Federal LCA Commons 저장소에서 2026-10-08 확보했다.

## USLCI

- 공개 GitHub 원본: [USLCI 1.2026-09.0 `.zolca`](https://github.com/FLCAC-admin/uslci-content/blob/dev/downloads/uslci_v1.2026-09.0_olca2_7_1.zolca), openLCA 2.7.1용. 이 파일을 `data/raw/uslci_v1.2026-09.0_olca2_7_1.zolca`로 저장한다.
- 분석 가능한 JSON-LD: [Federal LCA Commons USLCI 데이터셋](https://www.lcacommons.gov/lca-collaboration/National_Renewable_Energy_Laboratory/USLCI_Database_Public/datasets)의 버전을 1.2026-09.0으로 선택하고 **Download → as JSON-LD (openLCA 2.x)**를 선택한다. 받은 ZIP을 `data/raw/uslci_commons_export.zip`으로 저장한다. 사이트에서 직접 받을 수 없으면 `.zolca`를 openLCA 2.7.1에 불러온 후 JSON-LD로 내보낸다. 이 내보내기는 버전·구성에 따라 SHA가 달라질 수 있으므로 명세의 해시와 공정 ID를 확인한다.
- 2026년 9월 릴리스에서 내장 Electricity Baseline 라이브러리가 제거됐다. 별도 전력 공급자를 연결해야 한다. 이 계산은 연결 불가능한 전력을 `data/model.json`의 미국 전력 가정 계수로 대체했으므로 완전한 USLCI 제품 시스템이 아니다. [공식 릴리스 설명](https://github.com/FLCAC-admin/uslci-content/blob/dev/docs/release_info/press-release.md).
- 공개 예시 API 키는 USLCI JSON-LD 내보내기 때 작동했으나 같은 세션의 다음 요청에서 사용량 제한에 걸렸다. 재현 시 웹 페이지 다운로드나 로컬 `.zolca` 내보내기를 권장한다. 개인 API 키를 Git에 저장하거나 채팅으로 보내지 않는다.

## 영향평가 방법

- [FLCAC/USEPA LCIAformatter의 `IPCC_GWP_values.csv`](https://github.com/FLCAC-admin/LCIAformatter/blob/master/lciafmt/data/IPCC_GWP_values.csv), 소스 커밋 `48d19af11965994378e9febe0cca2d5822a0776d`. `data/raw/IPCC_GWP_values.csv`에 저장한다.
- [방법 변환 코드](https://github.com/FLCAC-admin/LCIAformatter/blob/master/lciafmt/ipcc.py)는 AR6의 원 출처를 IPCC WG1 Chapter 7 보충자료 Table 7.SM.7로 명시한다. 이 분석은 `AR6`/`GWP100` 행을 사용한다.
- USLCI JSON-LD의 공기 배출 원소 흐름을 이름 또는 CAS로 직접 매칭했다. 공식 Commons IPCC 라이브러리 JSON-LD를 가져와 동일 UUID로 조인한 계산은 아니다. 따라서 공식 openLCA 결과와의 동등성을 주장하지 않는다.

## 과제 전경 자료

- [과제 페이지](https://tiangong-lca-decision-lab.ecodino73.chatgpt.site/)와 `data/source/`의 README 체크리스트, 저장소 체크리스트, BOM CSV, 매핑 표 템플릿, 실행 명세 템플릿을 2026-10-08 가져왔다.
- BOM은 EU Electric Kettles preparatory study (2020), Task 4 Tables 4-3, 4-4, 4-8을 기초로 한 대표 구성이다. BC1은 상표 제품 데이터가 아니다.

## 공개 범위

Git에는 과제의 공개 BOM과 템플릿, 작성한 코드·매핑·가정·결과만 넣는다. USLCI `.zolca`, Commons JSON-LD 전체 내보내기, 방법 원본 다운로드, 토큰·인증 세션은 공개 저장소에 포함하지 않는다.
