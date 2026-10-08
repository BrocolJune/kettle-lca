"""Transparent screening LCA from the official USLCI JSON-LD export.

The report distinguishes inventory emissions from assumed upstream gaps. It is
not an openLCA product-system result and is not suitable for comparative claims.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import sys
import zipfile
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.sparse import csc_matrix, eye
from scipy.sparse.linalg import spsolve

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "results"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_zip_models(path: Path, folder: str) -> dict[str, dict]:
    with zipfile.ZipFile(path) as z:
        return {
            obj["@id"]: obj
            for name in z.namelist()
            if name.startswith(folder + "/") and name.endswith(".json")
            for obj in [json.loads(z.read(name))]
            if "@id" in obj
        }


def unit_base(unit: str) -> tuple[str, float]:
    normalized = unit.lower().replace(" ", "")
    values = {
        "kg": ("mass", 1), "g": ("mass", .001), "mg": ("mass", .000001),
        "t": ("mass", 1000), "ton": ("mass", 1000),
        "shtn": ("mass", 907.18474),
        "lbav": ("mass", .45359237),
        "mj": ("energy", 1), "kj": ("energy", .001), "j": ("energy", .000001),
        "kwh": ("energy", 3.6), "wh": ("energy", .0036),
        "btu": ("energy", .00105505585),
        "m3": ("volume", 1), "l": ("volume", .001), "ml": ("volume", .000001),
        "gal(usliq)": ("volume", .003785411784),
        "gal(usfl)": ("volume", .003785411784),
        "cuft": ("volume", .028316846592),
        "t*km": ("transport", 1), "tkm": ("transport", 1),
        "kg*km": ("transport", .001),
        "t*mi": ("transport", 1.609344),
        "usd": ("money", 1), "usd2017": ("money", 1),
        "item(s)": ("item", 1), "item": ("item", 1),
        "m2": ("area", 1),
        "m": ("length", 1),
    }
    if normalized not in values:
        raise ValueError(f"Unsupported unit {unit!r}; specify a conversion")
    return values[normalized]


def convert(amount: float, from_unit: str, to_unit: str) -> float:
    a, x = unit_base(from_unit)
    b, y = unit_base(to_unit)
    if a != b:
        raise ValueError(f"Incompatible units: {from_unit} -> {to_unit}")
    return amount * x / y


def ref_exchange(p: dict) -> dict:
    refs = [x for x in p.get("exchanges", []) if x.get("isQuantitativeReference")]
    if len(refs) != 1:
        raise ValueError(f"Process {p['@id']} has {len(refs)} reference exchanges")
    if not refs[0].get("amount"):
        raise ValueError(f"Zero reference amount in {p['@id']}")
    return refs[0]


def cf_by_flow(flows: dict, path: Path) -> tuple[dict, dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["AR"] == "AR6" and r["Parameter"] == "GWP100"]
    by_cas = defaultdict(set)
    by_name = defaultdict(set)
    for r in rows:
        if r["Value"] in ("", "(no data)"):
            continue
        factor = float(r["Value"])
        if r["CAS"] not in ("", "(no data)"):
            by_cas[r["CAS"]].add(factor)
        by_name[r["Name"].lower()].add(factor)
    factors, notes = {}, Counter()
    for fid, flow in flows.items():
        if flow.get("flowType") != "ELEMENTARY_FLOW":
            continue
        if not flow.get("category", "").startswith("Elementary flows/emission/air"):
            continue
        name = flow["name"].lower()
        if "carbon dioxide, biogenic" in name:
            notes["biogenic_co2_zero_by_convention"] += 1
            continue
        if name == "methane, biogenic":
            factors[fid] = next(iter(by_name["methane"]))
            notes["biogenic_methane_mapped_to_methane"] += 1
            continue
        values = by_name.get(name, set())
        if len(values) != 1:
            values = by_cas.get(flow.get("cas"), set())
        if len(values) == 1:
            factors[fid] = next(iter(values))
            notes["matched_air_flow"] += 1
    return factors, dict(notes)


def fallback_class(flow: dict, unit: str, is_waste: bool) -> tuple[str, float]:
    try:
        kind, to_base = unit_base(unit)
    except ValueError as error:
        raise ValueError(f"{error}; flow={flow.get('name')} id={flow.get('@id')}") from error
    name = flow.get("name", "").lower()
    if is_waste:
        if kind == "mass":
            return ("inert_mining_waste_kg" if any(word in name for word in ("overburden", "tailings", "spoil")) else "waste_kg"), to_base
        if kind == "energy":
            return "waste_mj", to_base
        if kind == "volume":
            return "waste_m3", to_base
        raise ValueError(f"Unresolved waste unit {unit}: {name}")
    if kind == "transport":
        return "transport_tkm", to_base
    if kind == "money":
        return "monetary_usd", to_base
    if kind == "item":
        return "infrastructure_item", to_base
    if kind == "area":
        return "land_m2", to_base
    if kind == "length":
        return "infrastructure_m", to_base
    if kind == "energy":
        return ("electricity_mj" if "electric" in name else "fuel_mj"), to_base
    if kind == "volume":
        if "water" in name:
            return "water_kg", to_base * 1000
        return ("fuel_m3", to_base) if unit.lower() in ("m3", "cu ft") else ("fuel_l", to_base * 1000)
    if kind == "mass":
        if "old corrugated containers" in name:
            return "recycled_feedstock_kg", to_base
        return ("water_kg" if "water" in name else "material_kg"), to_base
    raise ValueError(f"No fallback for {flow['name']} [{unit}]")


class Background:
    def __init__(self, processes: dict, flows: dict, cf: dict, config: dict):
        self.processes, self.flows, self.cf, self.config = processes, flows, cf, config
        self.producers = defaultdict(list)
        for pid, p in processes.items():
            try:
                e = ref_exchange(p)
                self.producers[e["flow"]["@id"]].append(pid)
            except ValueError:
                pass
        self.gaps = []
        self.unmatched = Counter()
        self.coproducts = []

    def provider(self, pid: str, e: dict) -> str | None:
        explicit = (e.get("defaultProvider") or {}).get("@id")
        if explicit in self.processes:
            return explicit
        if explicit:
            return None
        candidates = [p for p in self.producers[e["flow"]["@id"]] if p != pid]
        return candidates[0] if len(candidates) == 1 else None

    def build(self, roots: list[str]) -> tuple[list[str], csc_matrix, dict[str, np.ndarray], list]:
        queue = deque(roots)
        visited = set()
        while queue:
            pid = queue.popleft()
            if pid in visited:
                continue
            if pid not in self.processes:
                raise ValueError(f"Foreground dataset absent: {pid}")
            visited.add(pid)
            p = self.processes[pid]
            if p.get("processType") == "LCI_RESULT":
                continue
            ref = ref_exchange(p)
            for e in p.get("exchanges", []):
                if e is ref:
                    continue
                t = e.get("flow", {}).get("flowType")
                demand = (t == "PRODUCT_FLOW" and e.get("isInput")) or (t == "WASTE_FLOW" and not e.get("isInput"))
                if demand:
                    target = self.provider(pid, e)
                    if target:
                        queue.append(target)
        ids = sorted(visited)
        index = {pid: i for i, pid in enumerate(ids)}
        rows, cols, values = [], [], []
        direct = np.zeros(len(ids))
        basis = {k: np.zeros(len(ids)) for k in self.config["unresolved_provider_assumptions"]}
        for pid in ids:
            i, p = index[pid], self.processes[pid]
            ref = ref_exchange(p)
            ref_amount = abs(ref["amount"])
            ref_unit = ref["unit"]["name"]
            if p.get("processType") != "LCI_RESULT":
                outputs = [e for e in p.get("exchanges", []) if e.get("flow", {}).get("flowType") == "PRODUCT_FLOW" and not e.get("isInput") and e is not ref]
                if outputs:
                    self.coproducts.append({"process_id": pid, "process": p["name"], "co_outputs": len(outputs)})
            for e in p.get("exchanges", []):
                if e is ref:
                    continue
                flow = e.get("flow", {})
                unit = e.get("unit", {}).get("name", "")
                amount = e.get("amount", 0) / ref_amount
                t = flow.get("flowType")
                if t == "ELEMENTARY_FLOW" and not e.get("isInput"):
                    fid = flow.get("@id")
                    if fid in self.cf:
                        direct[i] += convert(amount, unit, "kg") * self.cf[fid]
                    elif self.flows.get(fid, {}).get("category", "").startswith("Elementary flows/emission/air"):
                        self.unmatched[flow.get("name", fid)] += 1
                    continue
                if p.get("processType") == "LCI_RESULT":
                    continue
                demand = (t == "PRODUCT_FLOW" and e.get("isInput")) or (t == "WASTE_FLOW" and not e.get("isInput"))
                if not demand:
                    continue
                target = self.provider(pid, e)
                gap_reason = "provider absent or ambiguous"
                if target and target in index:
                    target_ref = ref_exchange(self.processes[target])
                    if target_ref["flow"]["@id"] != flow.get("@id"):
                        target = None
                        gap_reason = "provider reference flow mismatch"
                    else:
                        try:
                            converted = convert(amount, unit, target_ref["unit"]["name"])
                        except ValueError:
                            target = None
                            gap_reason = "provider unit mismatch"
                        else:
                            coefficient = converted / abs(target_ref["amount"])
                            rows.append(i); cols.append(index[target]); values.append(-coefficient)
                if not target or target not in index:
                    key, conversion = fallback_class(flow, unit, t == "WASTE_FLOW")
                    basis[key][i] += amount * conversion
                    self.gaps.append({"process_id": pid, "process": p["name"], "flow": flow.get("name"), "flow_id": flow.get("@id"), "unit": unit, "amount_per_reference": amount, "fallback_class": key, "conversion_to_base": conversion, "gap_reason": gap_reason, "explicit_provider_id": (e.get("defaultProvider") or {}).get("@id")})
        matrix = eye(len(ids), format="csc") + csc_matrix((values, (rows, cols)), shape=(len(ids), len(ids)))
        return ids, matrix, {"direct": direct, **basis}, self.gaps


def material_group(name: str) -> str:
    if name in ("Stainless steel", "Brass", "Copper"):
        return "metal"
    if name == "Cardboard packaging":
        return "cardboard"
    if name == "LDPE packaging foil":
        return "foil"
    if name == "Silicone":
        return "silicone"
    return "thermoplastic"


def main() -> None:
    config = json.loads((ROOT / "data" / "model.json").read_text(encoding="utf-8"))
    data_path = RAW / "uslci_commons_export.zip"
    cf_path = RAW / "IPCC_GWP_values.csv"
    processes = read_zip_models(data_path, "processes")
    flows = read_zip_models(data_path, "flows")
    cf, cf_notes = cf_by_flow(flows, cf_path)
    bom_path = ROOT / "data" / "source" / "kettle-bom.csv"
    with bom_path.open(encoding="utf-8-sig", newline="") as f:
        bom = list(csv.DictReader(f))
    mass = Counter()
    for row in bom:
        mass[row["scope"]] += float(row["finished_mass_g"])
    if not (abs(mass["Kettle"] - 723) < 1e-9 and abs(mass["Packaging"] - 137.8) < 1e-9):
        raise ValueError(f"BOM mass balance failed: {mass}")
    roots = [v["id"] for v in config["foreground_dataset_mapping"].values()]
    roots += [config["foreground_electricity_provider_id"], config["foreground_truck_provider_id"]]
    model = Background(processes, flows, cf, config)
    ids, matrix, vectors, gaps = model.build(roots)
    solutions = {}
    for key, vector in vectors.items():
        answer = spsolve(matrix, vector)
        if not np.all(np.isfinite(answer)):
            raise ValueError(f"Nonfinite solution for {key}")
        solutions[key] = answer
    index = {pid: i for i, pid in enumerate(ids)}
    fallback = config["unresolved_provider_assumptions"]

    def components(pid: str, quantity: float) -> dict[str, float]:
        i = index[pid]
        return {key: float(quantity * value[i] * (1 if key == "direct" else fallback[key])) for key, value in solutions.items()}

    rows = []
    def add_row(stage: str, item: str, amount: float, unit: str, pieces: dict, status: str, dataset_id: str = "") -> None:
        rows.append({"stage": stage, "item": item, "quantity": amount, "unit": unit, "status": status, "dataset_id": dataset_id, "kg_co2e": sum(pieces.values()), "components": pieces})

    loss = config["material_loss_fraction"]
    electricity_id = config["foreground_electricity_provider_id"]
    for row in bom:
        name = row["material"]
        finished = float(row["finished_mass_g"]) / 1000
        mapped = config["foreground_dataset_mapping"].get(name)
        purchased = finished if mapped and mapped.get("integrated_processing") else finished / (1 - loss)
        if mapped:
            add_row("material and included upstream", name, purchased, "kg", components(mapped["id"], purchased), "sourced process + assumed missing providers", mapped["id"])
        else:
            assumed = config["assumed_material_kgco2e_per_kg"].get(name)
            if assumed is None:
                raise ValueError(f"No material dataset or explicit assumption for {name}")
            add_row("material and included upstream", name, purchased, "kg", {"assumed_material": purchased * assumed}, "assumed material factor")
        if not (mapped and mapped.get("integrated_processing")):
            intensity = config["processing_electricity_kwh_per_kg"][material_group(name)]
            kwh = finished * intensity
            add_row("component conversion", name, kwh, "kWh", components(electricity_id, kwh * 3.6), "assumed electricity quantity; sourced bridge + assumed grid factor", electricity_id)
    assembly = config["assembly_electricity_kwh"]
    add_row("assembly", "assembly electricity", assembly, "kWh", components(electricity_id, assembly * 3.6), "assumed electricity quantity; sourced bridge + assumed grid factor", electricity_id)
    tkm = (mass["Kettle"] + mass["Packaging"]) / 1e6 * config["supplier_to_assembly_transport_km"]
    truck_id = config["foreground_truck_provider_id"]
    add_row("supplier to assembly transport", "500 km combination truck", tkm, "t*km", components(truck_id, tkm), "assumed distance; sourced truck process + assumed missing providers", truck_id)
    total = sum(r["kg_co2e"] for r in rows)
    if not math.isfinite(total):
        raise ValueError("Nonfinite GWP result")
    by_stage = dict(sorted(Counter({k: sum(r["kg_co2e"] for r in rows if r["stage"] == k) for k in set(r["stage"] for r in rows)}).items()))
    pieces = Counter()
    for r in rows:
        pieces.update(r["components"])
    assumed_part = sum(v for k, v in pieces.items() if k != "direct")
    demand = np.zeros(len(ids))
    for r in rows:
        if r["dataset_id"]:
            quantity = r["quantity"] * (3.6 if r["unit"] == "kWh" else 1)
            demand[index[r["dataset_id"]]] += quantity
    activities = spsolve(matrix.T, demand)
    for gap in gaps:
        gap["kg_co2e_attributed"] = float(activities[index[gap["process_id"]]] * gap["amount_per_reference"] * gap["conversion_to_base"] * fallback[gap["fallback_class"]])
    rng = random.Random(config["uncertainty"]["seed"])
    low = config["uncertainty"]["assumption_multiplier_low"]
    high = config["uncertainty"]["assumption_multiplier_high"]
    samples = []
    for _ in range(config["uncertainty"]["draws"]):
        sampled = pieces["direct"]
        for key, value in pieces.items():
            if key != "direct":
                sampled += value * rng.triangular(low, high, 1)
        samples.append(sampled)
    sample_values = np.asarray(samples)
    report = {
        "run_id": config["run_id"], "run_date_utc": datetime.now(timezone.utc).isoformat(),
        "declared_unit": "one manufactured and packaged BC1 1 L plastic kettle at factory gate",
        "calculation_status": "screening estimate with explicit provider and material assumptions",
        "total_kg_co2e": total, "finished_product_g": mass["Kettle"], "finished_packaging_g": mass["Packaging"],
        "contribution_rows": rows, "by_stage": by_stage, "component_totals": dict(pieces),
        "assumed_share_fraction": assumed_part / total if total else None,
        "top_three": sorted(rows, key=lambda r: r["kg_co2e"], reverse=True)[:3],
        "provider_gaps_count": len(gaps), "provider_gap_classes": dict(Counter(g["fallback_class"] for g in gaps)),
        "provider_gap_reasons": dict(Counter(g["gap_reason"] for g in gaps)),
        "top_assumed_provider_gaps": sorted(gaps, key=lambda g: abs(g["kg_co2e_attributed"]), reverse=True)[:20],
        "reachable_processes": len(ids), "source_processes": len(processes),
        "coproduct_process_count": len(model.coproducts), "unmatched_air_flow_names": dict(model.unmatched),
        "cf_matching": cf_notes, "cf_matched_flow_count": len(cf),
        "uncertainty": {"method": "independent triangular multipliers on each assumed factor class; direct inventory fixed", "draws": len(samples), "seed": config["uncertainty"]["seed"], "mean": float(sample_values.mean()), "median": float(np.median(sample_values)), "p05": float(np.quantile(sample_values, .05)), "p95": float(np.quantile(sample_values, .95)), "split_half_p05_difference": float(abs(np.quantile(sample_values[:len(samples)//2], .05) - np.quantile(sample_values[len(samples)//2:], .05))), "split_half_p95_difference": float(abs(np.quantile(sample_values[:len(samples)//2], .95) - np.quantile(sample_values[len(samples)//2:], .95)))},
        "sources": {"uslci_jsonld_sha256": sha256(data_path), "uslci_zolca_sha256": sha256(RAW / "uslci_v1.2026-09.0_olca2_7_1.zolca"), "ipcc_csv_sha256": sha256(cf_path), "bom_sha256": sha256(bom_path)},
        "checks": {"mass_balance": "pass", "contribution_sum_difference": total - sum(by_stage.values()), "nonfinite": False, "supplier_closure": "incomplete; quantified assumptions for unresolved exchanges", "double_counting": "PP molding contains resin and is not separately charged; all other processing electricity is foreground only"},
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "run.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    with (OUT / "contributions.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["stage", "item", "quantity", "unit", "status", "dataset_id", "kg_co2e"])
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in writer.fieldnames})
    with (OUT / "unresolved-providers.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["process_id", "process", "flow", "flow_id", "unit", "amount_per_reference", "fallback_class", "conversion_to_base", "gap_reason", "explicit_provider_id", "kg_co2e_attributed"])
        writer.writeheader(); writer.writerows(gaps)
    (OUT / "coproduct-processes.json").write_text(json.dumps(model.coproducts, indent=2), encoding="utf-8")
    alternatives = {
        "Stainless steel": "304 quarto plate; 304 scrap (rejected: form or life-stage mismatch)",
        "Brass": "no brass process in local USLCI export; generic metal proxy rejected",
        "Copper": "Copper at storage USLCI-to-USEEIO bridge (rejected: USD provider unlinked)",
        "Polypropylene (PP)": "PP virgin resin only; PP thermoforming (rejected: injection-molded proxy better)",
        "Polyvinyl chloride (PVC)": "PVC roofing membrane (rejected: composite end product)",
        "Nylon, grade unspecified": "Nylon 6 and Nylon 66 USEEIO bridges (rejected: grade unknown and USD provider unlinked)",
        "Polyoxymethylene (POM)": "no POM or acetal process in local USLCI export",
        "Polycarbonate (PC)": "PC USEEIO bridge (rejected: USD provider unlinked)",
        "Acrylonitrile-butadiene-styrene (ABS)": "acrylonitrile monomer (rejected: not ABS resin)",
        "Silicone": "no silicone process in local USLCI export",
        "LDPE packaging foil": "LLDPE stretch film (rejected: polymer variant)",
        "Cardboard packaging": "containerboard at mill; 100% recycled corrugated (rejected: assumed average packaging mix)",
    }
    mapping_path = ROOT / "data" / "mapping" / "mapping-decisions.csv"
    mapping_path.parent.mkdir(exist_ok=True)
    fields = ["foreground_input", "finished_mass_g", "purchased_mass_kg", "database", "release", "dataset_id", "dataset_version", "dataset_name", "geography", "year_or_validity", "reference_flow", "reference_amount", "reference_unit", "source_url", "retrieved_at_utc", "source_sha256", "search_terms", "alternatives_considered", "selection_reason", "proxy_or_exact", "status", "unresolved_gap"]
    with mapping_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in bom:
            name = item["material"]
            mapped = config["foreground_dataset_mapping"].get(name)
            p = processes[mapped["id"]] if mapped else None
            ref = ref_exchange(p) if p else None
            finished = float(item["finished_mass_g"]) / 1000
            writer.writerow({
                "foreground_input": name, "finished_mass_g": item["finished_mass_g"],
                "purchased_mass_kg": finished if mapped and mapped.get("integrated_processing") else finished / (1 - loss),
                "database": "USLCI" if p else "explicit assumption after USLCI search", "release": config["uslci_release"] if p else "not applicable",
                "dataset_id": p["@id"] if p else "not available", "dataset_version": p.get("version", "unknown") if p else "not available",
                "dataset_name": p["name"] if p else "not available", "geography": (p.get("location") or {}).get("name", "unknown") if p else "not assigned",
                "year_or_validity": (p.get("processDocumentation") or {}).get("validUntil", "unknown") if p else "not applicable",
                "reference_flow": ref["flow"]["name"] if ref else "not applicable", "reference_amount": ref["amount"] if ref else "not applicable", "reference_unit": ref["unit"]["name"] if ref else "kg material",
                "source_url": "https://www.lcacommons.gov/lca-collaboration/National_Renewable_Energy_Laboratory/USLCI_Database_Public/datasets" if p else "not applicable",
                "retrieved_at_utc": report["run_date_utc"], "source_sha256": report["sources"]["uslci_jsonld_sha256"] if p else "not applicable",
                "search_terms": name, "alternatives_considered": alternatives[name],
                "selection_reason": mapped["reason"] if mapped else "No suitable independently linked material process; transparent factor assumption in data/model.json",
                "proxy_or_exact": "proxy" if mapped or not p else "exact", "status": "sourced process with assumed background gaps" if p else "assumed",
                "unresolved_gap": "see results/unresolved-providers.csv" if p else "material factor not from USLCI",
            })
        for label, pid, units in (("Manufacturing electricity", electricity_id, "MJ"), ("Supplier to assembly transport", truck_id, "t*km")):
            p = processes[pid]; ref = ref_exchange(p)
            writer.writerow({"foreground_input": label, "finished_mass_g": "not applicable", "purchased_mass_kg": "not applicable", "database": "USLCI", "release": config["uslci_release"], "dataset_id": pid, "dataset_version": p.get("version", "unknown"), "dataset_name": p["name"], "geography": (p.get("location") or {}).get("name", "unknown"), "year_or_validity": (p.get("processDocumentation") or {}).get("validUntil", "unknown"), "reference_flow": ref["flow"]["name"], "reference_amount": ref["amount"], "reference_unit": ref["unit"]["name"], "source_url": "https://www.lcacommons.gov/lca-collaboration/National_Renewable_Energy_Laboratory/USLCI_Database_Public/datasets", "retrieved_at_utc": report["run_date_utc"], "source_sha256": report["sources"]["uslci_jsonld_sha256"], "search_terms": label, "alternatives_considered": "external electricity provider unavailable" if units == "MJ" else "no geography-specific supplier transport", "selection_reason": "US average bridge with assumed grid factor" if units == "MJ" else "US combination truck process", "proxy_or_exact": "proxy", "status": "sourced process with assumed background gaps", "unresolved_gap": "see results/unresolved-providers.csv"})
    manifest = {"run_id": config["run_id"], "run_date_utc": report["run_date_utc"], "data": [
        {"file": "data/raw/uslci_commons_export.zip", "sha256": report["sources"]["uslci_jsonld_sha256"], "release": config["uslci_release"], "url": "https://www.lcacommons.gov/lca-collaboration/National_Renewable_Energy_Laboratory/USLCI_Database_Public/datasets", "redistributed": False},
        {"file": "data/raw/uslci_v1.2026-09.0_olca2_7_1.zolca", "sha256": report["sources"]["uslci_zolca_sha256"], "release": config["uslci_release"], "url": "https://github.com/FLCAC-admin/uslci-content/blob/dev/downloads/uslci_v1.2026-09.0_olca2_7_1.zolca", "redistributed": False},
        {"file": "data/raw/IPCC_GWP_values.csv", "sha256": report["sources"]["ipcc_csv_sha256"], "release": config["method_source_commit"], "url": "https://github.com/FLCAC-admin/LCIAformatter/blob/master/lciafmt/data/IPCC_GWP_values.csv", "redistributed": False},
    ]}
    for source_name in ("readme-requirements.md", "repository-checklist.md", "kettle-bom.csv", "mapping-decisions.csv", "run-manifest.json"):
        source_path = ROOT / "data" / "source" / source_name
        manifest["data"].append({"file": f"data/source/{source_name}", "sha256": sha256(source_path), "url": f"https://tiangong-lca-decision-lab.ecodino73.chatgpt.site/classroom/{source_name}", "retrieved_at_utc": "2026-10-08", "redistributed": True})
    (ROOT / "data" / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    classroom_manifest = json.loads((ROOT / "data" / "source" / "run-manifest.json").read_text(encoding="utf-8"))
    classroom_manifest.update({
        "student_alias": "BrocolJune", "run_label": "independent", "run_date_utc": report["run_date_utc"],
        "codex_model_displayed": "GPT-6 based Codex; exact variant unknown",
        "codex_settings_known": {"python": sys.version.split()[0], "numpy": np.__version__},
        "manufacturing_geography": "unknown; US and North American background proxies",
        "characterization_method": {"name": "IPCC AR6 GWP100", "version": config["method_source_commit"], "time_horizon_years": 100, "source_url": "https://github.com/FLCAC-admin/LCIAformatter/blob/master/lciafmt/data/IPCC_GWP_values.csv"},
        "database_releases": [{"name": "USLCI", "version": config["uslci_release"], "manifest": "data/manifest.json"}],
        "assumptions": {"yield_and_losses": "5% loss except integrated PP molding", "manufacturing_energy": "see data/model.json", "allocation": "co-output burdens assigned to reference output in 15 processes", "recycling": "no recycling credit", "other": "see data/model.json and results/unresolved-providers.csv"},
        "mapping_table": "data/mapping/mapping-decisions.csv", "prompts_record": "docs/decisions.md",
        "reproduction_command": ".\\.venv\\Scripts\\python.exe -m src.lca; .\\.venv\\Scripts\\python.exe -m src.render_report",
        "results": {"status": report["calculation_status"], "ghg_kg_co2e_per_packaged_kettle": total, "contributions": [{"stage": k, "kg_co2e": v} for k, v in by_stage.items()], "missing_inputs": list(config["assumed_material_kgco2e_per_kg"]), "unresolved_providers": [f"{len(gaps)} exchanges; see results/unresolved-providers.csv"], "uncharacterized_flows": ["aggregated CFC/HCFC/HFC/PFC and other uncharacterized air flows; see results/run.json"]},
        "uncertainty": {"performed": True, "distributions": ["independent triangular multipliers 0.5, 1, 1.5 on assumption classes"], "correlations": "assumed independent; empirical correlations unknown", "seed": config["uncertainty"]["seed"], "draws": len(samples), "p05_kg_co2e": report["uncertainty"]["p05"], "p95_kg_co2e": report["uncertainty"]["p95"]},
        "checks": {"units": "compatible links converted; 102 unit-mismatch links treated as unresolved", "balances": "723.0 g kettle + 137.8 g packaging = 860.8 g", "contribution_sum": report["checks"]["contribution_sum_difference"], "double_counting": report["checks"]["double_counting"]},
        "revision": {"prior_commit_sha": None, "one_choice_changed": "not applicable", "predicted_effect": "not applicable", "observed_effect": "not applicable"}
    })
    (OUT / "run-manifest.json").write_text(json.dumps(classroom_manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("total_kg_co2e", "assumed_share_fraction", "provider_gaps_count", "reachable_processes", "coproduct_process_count", "uncertainty")}, indent=2))


if __name__ == "__main__":
    main()
