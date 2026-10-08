"""Render the completed screening run as a portable standalone HTML report."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"


def h(value: object) -> str:
    return html.escape(str(value), quote=True)


def n(value: float, digits: int = 3) -> str:
    return f"{value:,.{digits}f}"


def table(headers: list[str], rows: list[list[object]]) -> str:
    head = "".join(f"<th scope='col'>{h(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{h(x)}</td>" for x in row) + "</tr>" for row in rows)
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def main() -> None:
    run = json.loads((OUT / "run.json").read_text(encoding="utf-8"))
    model = json.loads((ROOT / "data" / "model.json").read_text(encoding="utf-8"))
    with (ROOT / "data" / "mapping" / "mapping-decisions.csv").open(encoding="utf-8", newline="") as f:
        mapping = list(csv.DictReader(f))
    rows = run["contribution_rows"]
    total = run["total_kg_co2e"]
    stage_rows = [[stage, n(value), n(value / total * 100, 1) + "%"] for stage, value in run["by_stage"].items()]
    contribution_rows = [[r["stage"], r["item"], n(r["quantity"], 4) + " " + r["unit"], n(r["kg_co2e"], 4), r["status"]] for r in rows]
    assumption_rows = [["Loss before finished material", n(model["material_loss_fraction"] * 100, 1) + "%", "assumed", "Except integrated PP molding; determines purchased mass"],
                       ["Assembly electricity", n(model["assembly_electricity_kwh"], 2) + " kWh/kettle", "assumed", "Factory assembly energy; product use electricity excluded"],
                       ["Supplier-to-assembly transport", str(model["supplier_to_assembly_transport_km"]) + " km", "assumed", "0.8608 kg delivered by combination truck"]]
    assumption_rows += [["Conversion electricity: " + k, n(v, 2) + " kWh/kg", "assumed", "PP injection dataset includes its own conversion; other materials only"] for k, v in model["processing_electricity_kwh_per_kg"].items()]
    assumption_rows += [["Material factor: " + k, n(v, 2) + " kg CO₂-eq/kg", "assumed", "No suitable independently linked USLCI material process"] for k, v in model["assumed_material_kgco2e_per_kg"].items()]
    assumption_rows += [["Missing provider: " + k, n(v, 4) + " kg CO₂-eq/unit", "assumed", "Applied only to unresolved technosphere exchanges"] for k, v in model["unresolved_provider_assumptions"].items()]
    mapping_rows = [[r["foreground_input"], r["dataset_name"], r["dataset_id"], r["geography"], r["status"]] for r in mapping]
    gap_rows = [[g["process"], g["flow"], g["fallback_class"], n(g["kg_co2e_attributed"], 4)] for g in run["top_assumed_provider_gaps"][:10]]
    max_value = max(r["kg_co2e"] for r in rows)
    bars = "".join(
        f"<div class='bar-row'><span>{h(r['item'])}</span><div class='bar-track'><div class='bar' style='width:{max(0, r['kg_co2e']) / max_value * 100:.1f}%'></div></div><b>{n(r['kg_co2e'], 3)}</b></div>"
        for r in sorted(rows, key=lambda r: r["kg_co2e"], reverse=True)[:12]
    )
    top_three = ", ".join(f"{r['item']} ({n(r['kg_co2e'])})" for r in run["top_three"])
    unknown_gases = [name for name in run["unmatched_air_flow_names"] if name in ("Chlorofluorocarbons", "Hydrochlorofluorocarbons", "Perfluorocarbons", "Hydrofluorocarbons")]
    html_doc = f"""<!doctype html>
<html lang='ko'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>BC1 1 L 전기주전자 공장 출하 전 LCA · {h(run['run_id'])}</title>
<style>
:root{{--ink:#16304a;--muted:#5b6d7e;--line:#dbe4eb;--paper:#f6f8fa;--blue:#1777a7;--accent:#e8f4f8;--warning:#fff5db}}
*{{box-sizing:border-box}} body{{font-family:system-ui,'Malgun Gothic',sans-serif;color:var(--ink);margin:0;background:var(--paper);line-height:1.58}}
main{{max-width:1120px;margin:auto;padding:28px 30px 60px;background:white}} h1{{font-size:2rem;margin:.2rem 0}} h2{{font-size:1.36rem;border-bottom:2px solid var(--line);padding-bottom:.35rem;margin-top:2.2rem}} h3{{font-size:1.05rem;margin-top:1.5rem}}
p{{margin:.7rem 0}} .eyebrow{{letter-spacing:.12em;text-transform:uppercase;color:var(--blue);font-weight:700;font-size:.78rem}} .lead{{font-size:1.05rem;color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:22px 0}} .card{{padding:17px;background:var(--accent);border-radius:10px}} .card strong{{display:block;font-size:1.45rem}} .card span{{display:block;color:var(--muted);font-size:.88rem}}
.notice{{background:var(--warning);border-left:5px solid #d99a00;padding:13px 16px;border-radius:5px}} .boundary{{display:flex;gap:7px;flex-wrap:wrap;align-items:center;margin:1rem 0}} .boundary span{{background:#eaf2f6;padding:8px 11px;border-radius:6px}} .boundary em{{color:var(--blue);font-style:normal}}
.table-wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:.84rem;margin:10px 0 18px}} th,td{{border:1px solid var(--line);padding:8px 9px;text-align:left;vertical-align:top}} th{{background:#edf3f6}} tr:nth-child(even) td{{background:#fafcfd}} code{{background:#f0f3f5;padding:2px 4px;border-radius:3px}} a{{color:#096d9b}}
.bar-row{{display:grid;grid-template-columns:minmax(155px,240px) 1fr 75px;gap:10px;align-items:center;margin:6px 0;font-size:.88rem}} .bar-track{{height:17px;background:#eaf0f3;border-radius:4px}} .bar{{height:100%;background:#2783a5;border-radius:4px}} .bar-row b{{text-align:right}}
.small{{font-size:.84rem;color:var(--muted)}} ul{{padding-left:1.3rem}} footer{{border-top:1px solid var(--line);margin-top:2.5rem;padding-top:1rem;color:var(--muted);font-size:.8rem}}
@media(max-width:700px){{main{{padding:18px}}.grid{{grid-template-columns:1fr}}.bar-row{{grid-template-columns:120px 1fr 65px}}}}
@media print{{body{{background:white}}main{{padding:0;max-width:none}}a{{color:inherit}}}}
</style></head><body><main>
<div class='eyebrow'>Screening life cycle assessment · Independent run</div>
<h1>BC1 1 L 전기주전자 생산 단계 LCA</h1>
<p class='lead'>원자재 공급 → 부품 가공 → 조립 → 포장, 공장 출하 시점. 주전자 사용 중 전력 소비와 제품 사용 후 폐기는 제외.</p>
<div class='grid'><div class='card'><strong>{n(total,2)} kg CO₂-eq</strong><span>포장된 주전자 1대 · IPCC AR6 GWP100</span></div><div class='card'><strong>{n(run['assumed_share_fraction']*100,1)}%</strong><span>수치 결과 중 명시적 가정 기여</span></div><div class='card'><strong>{run['provider_gaps_count']}</strong><span>가정으로 보완한 미연결 공급자 교환</span></div></div>
<p class='notice'><strong>해석 주의.</strong> 이 결과는 USLCI 공정 인벤토리와 공개 IPCC 계수를 이용한 스크리닝 추정이다. 황동·구리·나일론·POM·PC·실리콘 재료 계수, 외부 전력 공급자, 일부 생산 및 처리 흐름에 가정값을 사용했다. 제품 인증용 수치나 다른 주전자와의 비교 주장에 사용하면 안 된다.</p>
<p class='small'>실행 ID: {h(run['run_id'])} · 계산일(UTC): {h(run['run_date_utc'])} · 학생 공개 별칭: BrocolJune</p>
<h2>1. 목적과 경계</h2>
<p>선언 단위는 <strong>제조·포장을 마친 BC1 1 L 플라스틱 전기주전자 1대</strong>이다. BC1은 대표 모델이며 실제 상표 제품을 뜻하지 않는다. 제조 위치는 미지정이다. 사용한 공정은 주로 미국 또는 북미 데이터를 지역 대리값으로 사용한다.</p>
<div class='boundary'><span>원자재</span><em>→</em><span>부품 가공</span><em>→</em><span>조립</span><em>→</em><span>포장</span><em>→</em><span>공장 출하</span></div>
<p><strong>제외:</strong> 고객 운송, 제품 사용 전력, 제품 수리·세척, 사용 후 재활용·매립·소각. 생산 공정의 자체 전력과 제조 스크랩 처리 부담은 생산 경계에 포함한다. 공급자에서 조립 공장까지 500 km 화물운송은 별도 가정으로 포함한다.</p>
<p>BOM 검산: 본체 {n(run['finished_product_g'],1)} g + 포장 {n(run['finished_packaging_g'],1)} g = {n(run['finished_product_g']+run['finished_packaging_g'],1)} g. 출처: 과제 사이트의 BC1 BOM, EU Electric Kettles preparatory study (2020), Task 4 Tables 4-3/4-4/4-8를 기초로 한 대표 구성.</p>
<h2>2. 영향평가 결과</h2>
<p>기준 결과는 <strong>{n(total,4)} kg CO₂-eq/대</strong>이다. 상위 기여 요인: {h(top_three)} (각 값 kg CO₂-eq). 전체 기여도는 아래 표와 <a href='contributions.csv'>CSV</a>에 있다.</p>
{bars}
<h3>단계별 합계</h3>{table(['단계','kg CO₂-eq/대','총량 비중'],stage_rows)}
<h3>전체 투입별 기여도</h3>{table(['단계','투입','모델 양','kg CO₂-eq/대','자료 상태'],contribution_rows)}
<h2>3. 투입 데이터와 가정</h2>
<p>완제품 질량을 구매 투입량으로 바꿀 때 PP 사출 성형 공정에 내장된 3.4% 수지 투입은 그대로 사용하고 중복 추가하지 않았다. 나머지 재료는 일률적으로 5% 손실을 가정하여 구매량 = 완성 질량 ÷ 0.95로 계산했다. 모든 원자재의 양과 데이터셋 결정은 <a href='../data/mapping/mapping-decisions.csv'>매핑 표</a>에 있다.</p>
{table(['가정 항목','값','상태','적용 설명'],assumption_rows)}
<p>위의 수율, 조립 전력, 가공 전력, 운송 거리, 외부 전력 계수, 누락 재료 및 공급자 계수는 측정치가 아니라 모델 가정이다. 가격 기반 브리지의 USD 연도·구매자/기초가격 변환 정보가 없어 직접 재료계수로 채택하지 않았다.</p>
<h2>4. 배경 데이터와 계산 방법</h2>
<p>USLCI <strong>{h(model['uslci_release'])}</strong> JSON-LD에서 사용한 기준 재료·전력·운송 공정을 추출했다. 연결된 383개 공정에 대해 단위공정 직접 배출을 정규화하고, 동일 제품 흐름·호환 단위의 공급자를 연결했다. 공급자별 공정 투입 행렬을 M이라 하면 <code>(I − M)x = d + q</code>를 희소 선형계로 풀었다. d는 공정의 직접 GWP100, q는 미연결 공급자별 가정 기여다. 전경 투입량 f에 대해 총량은 <code>fᵀx</code>이다. 누락 흐름을 0으로 취급하지 않았다.</p>
<p>특성화: FLCAC LCIAformatter 공개 표의 IPCC AR6 GWP100, 100년 시간 범위, kg CO₂-eq/kg 기체. 공기 배출 흐름의 이름 또는 CAS를 일치시켰고, 생물기원 CO₂는 0으로, 생물기원 CH₄는 해당 표의 CH₄ 계수 27.9로 처리했다. 총 {run['cf_matched_flow_count']}개 공기 흐름 UUID에 계수를 연결했다. 집계형 CFC/HCFC/HFC/PFC 흐름은 단일 물질이 아니어서 특성화하지 않았다.</p>
<p>배분과 재활용: 원 데이터의 기본 배분 설정을 따르되, 연결 그래프의 다산출 공정 {run['coproduct_process_count']}개에서는 추가 배분을 실행하지 않고 기준 산출물에 전체 잔여 부담을 귀속했다. 이는 보수적 단순화이며 원 데이터의 배분 결과와 다를 수 있다. 재활용 크레딧은 부여하지 않았다. 원 데이터에 포함된 직접 폐기·운송 부담과 별도 전경 부담의 중복 가능성은 공정별로 검토해야 한다.</p>
<h3>공정 매핑 요약</h3>{table(['BOM/서비스','USLCI 선택 공정 또는 가정','UUID','지역','상태'],mapping_rows)}
<h2>5. 연결 공백과 한계</h2>
<p>383개 연결 대상 공정에서 미해결 공급자 교환이 {run['provider_gaps_count']}건이었다. 사유: {h(run['provider_gap_reasons'])}. 가정 분류별 전체 건수와 각 교환의 영향은 <a href='unresolved-providers.csv'>상세 CSV</a>를 참조한다. 상위 미연결 항목은 다음과 같다.</p>
{table(['소속 공정','미연결 흐름','가정 분류','kg CO₂-eq/대'],gap_rows)}
<p>결과 중 USLCI 직접 인벤토리 특성화가 {n(run['component_totals']['direct'],3)} kg CO₂-eq, 명시적 가정 부분이 {n(total-run['component_totals']['direct'],3)} kg CO₂-eq이다. 전력 공급자 연결, 다산출 배분, 제조 지역, 플라스틱 등급과 실제 가공·스크랩 데이터가 부족하다. 공기 배출 중 {len(run['unmatched_air_flow_names'])}개 이름은 이 GWP100 방법에 특성화계수가 없거나 생물기원 CO₂ 정책으로 0 처리되었다. 그중 집계형 온실가스 이름: {h(', '.join(unknown_gases) or '없음')}. 따라서 총량에 하방 누락이 있을 수 있다.</p>
<h2>6. 불확실성과 민감도</h2>
<p>가정 계수 분류마다 독립적인 삼각분포 배수 0.5–1.5(최빈 1)를 적용해 {run['uncertainty']['draws']:,}회 추출했다. 시드 {run['uncertainty']['seed']}. 조건부 평균 {n(run['uncertainty']['mean'])}, 중앙값 {n(run['uncertainty']['median'])}, P05–P95 <strong>{n(run['uncertainty']['p05'])}–{n(run['uncertainty']['p95'])} kg CO₂-eq/대</strong>. 전·후반 표본의 P05/P95 차이는 각각 {n(run['uncertainty']['split_half_p05_difference'],4)}/{n(run['uncertainty']['split_half_p95_difference'],4)} kg CO₂-eq다. 이 구간은 가정 계수에 둔 임의 분포를 전제로 한 것이며, 모델 구조, 배분, 누락 가스, 수율, 데이터셋 선택의 불확실성을 포함하지 않는다. 독립 가정이라는 선택도 실제 상관성을 반영하지 않는다.</p>
<h2>7. 재현과 자료 출처</h2>
<p>Windows ARM64, Python 3.13, NumPy 2.1.3, SciPy 1.15.3. 저장소 루트에서 <code>python -m venv --system-site-packages .venv</code>, <code>.\\.venv\\Scripts\\python.exe -m src.lca</code>, <code>.\\.venv\\Scripts\\python.exe -m src.render_report</code>를 실행한다. 원본 ZIP과 방법 CSV는 <code>data/raw/</code>에 두며 공개 Git 기록에서 제외한다. 정확한 파일 이름·URL·SHA256은 <a href='../data/manifest.json'>자료 명세</a>에 있다. GitHub의 `.zolca` 원본은 openLCA에서 JSON-LD로 내보낼 수 있다.</p>
<p>출처: <a href='https://github.com/FLCAC-admin/uslci-content/blob/dev/docs/release_info/release-downloads.md'>USLCI 릴리스 다운로드</a>, <a href='https://www.lcacommons.gov/lca-collaboration/National_Renewable_Energy_Laboratory/USLCI_Database_Public/datasets'>Federal LCA Commons USLCI</a>, <a href='https://github.com/FLCAC-admin/LCIAformatter/blob/master/lciafmt/data/IPCC_GWP_values.csv'>FLCAC IPCC 계수 표</a>, <a href='https://tiangong-lca-decision-lab.ecodino73.chatgpt.site/'>과제 자료</a>. 본 보고서와 산출물은 원본 데이터베이스를 재배포하지 않는다.</p>
<h2>8. 검산과 결론</h2>
<p>완제품·포장 질량 검산: 통과. 기여도 합계 차이: {n(run['checks']['contribution_sum_difference'],8)} kg CO₂-eq. PP 수지의 이중계산 방지: 별도 PP 수지 투입 없음. 공급자 폐쇄성: 실패(641개 연결 공백을 가정으로 대체). 완전한 GWP 특성화: 실패(집계형 온실가스 등 미특성화). 이 숫자는 데이터 공백이 큰 생산 단계 스크리닝 결과로 해석한다.</p>
<footer>기계 생성 보고서 · {h(run['run_id'])} · 독립 실행 결과 · 범위: 공장 출하 이전만</footer>
</main></body></html>"""
    (OUT / "report.html").write_text(html_doc, encoding="utf-8")
    print(OUT / "report.html")


if __name__ == "__main__":
    main()
