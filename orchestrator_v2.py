# """
# orchestrator.py  (v2)
# =====================
# Generic Investment ETL — 10 AI Agents
# Supports: Claude | Gemini | Ollama   (any combination + fallback chain)
# Accepts:  ANY rule-mapping Excel + ANY input data Excel

# Usage (CLI):
#   python orchestrator.py \
#     --input   path/to/data.xlsx \
#     --rules   path/to/rules.xlsx \
#     --out     path/to/output.xlsx \
#     --provider gemini \
#     --model   gemini-2.0-flash \
#     --fallback claude \
#     --ollama-host http://localhost:11434

#   # Ollama example:
#   python orchestrator.py --provider ollama --model llama3.2 \
#     --input data.xlsx --rules rules.xlsx

#   # Gemini primary, Claude fallback:
#   python orchestrator.py --provider gemini --fallback claude \
#     --input data.xlsx --rules rules.xlsx

# Agent flow:
#   1  SchemaAnalyzerAgent       — NLP: classify input schema
#   2  RuleInterpreterAgent      — NLP: English rules → structured ops
#   3  ArithmeticPrecisionAgent  — Deterministic: validate/route to BigDecimal
#   4  DBMappingAgent            — Deterministic: resolve DB lookups
#   5  OutputMappingAgent        — Deterministic: execute rules → output rows
#   6  DriftDetectionAgent       — NLP: detect systematic errors
#   7  RuleOptimizationAgent     — NLP: suggest improvements
#   8  TestGenerationAgent       — NLP generate + deterministic run (in-memory)
#   9  AnomalyDetectionAgent     — NLP: flag suspicious output values
#   10 RuntimeTestValidatorAgent — compute expected + validate actual Excel cell-by-cell
# """

# from __future__ import annotations
# import argparse, json, sys, os
# from datetime import datetime, timezone
# from pathlib import Path
# from decimal import Decimal

# import pandas as pd
# from openpyxl import Workbook
# from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
# from openpyxl.utils import get_column_letter

# sys.path.insert(0, os.path.dirname(__file__))

# from llm_router import LLMRouter
# from agents.agents import (
#     SchemaAnalyzerAgent, RuleInterpreterAgent, ArithmeticPrecisionAgent,
#     DBMappingAgent, OutputMappingAgent, DriftDetectionAgent,
#     RuleOptimizationAgent, TestGenerationAgent, AnomalyDetectionAgent,
#     RuntimeTestValidatorAgent,
# )


# # ── Helpers ───────────────────────────────────────────────────────────────────

# def banner(msg: str):
#     w = 65
#     print(f"\n{'═'*w}\n  {msg}\n{'═'*w}")


# def read_rule_mapping(path: str) -> tuple[list[str], list[dict]]:
#     """
#     Auto-detect rule mapping Excel format.
#     Expected columns: output_col | business_rule | input_columns
#     Tries to detect header row automatically.
#     """
#     df = pd.read_excel(path, header=None, dtype=str).fillna("")
#     # Detect header row: first row that contains multiple non-numeric entries
#     header_row = 0
#     for i, row in df.iterrows():
#         non_num = sum(1 for v in row if v and not _is_number(str(v)))
#         if non_num >= 2:
#             header_row = i
#             break
#     df = pd.read_excel(path, header=header_row, dtype=str).fillna("")
#     df.columns = [str(c).strip() for c in df.columns]
#     # Map to canonical names regardless of original column headers
#     cols = list(df.columns)
#     df.columns = ["output_col", "business_rule", "input_columns"] + cols[3:]
#     df = df[df["output_col"].str.strip() != ""]
#     output_columns = df["output_col"].tolist()
#     rules = df[["output_col","business_rule","input_columns"]].to_dict(orient="records")
#     return output_columns, rules


# def read_input_data(path: str) -> tuple[list[str], list[dict]]:
#     """Read input Excel — returns (columns, rows_as_dicts)."""
#     df = pd.read_excel(path, dtype=str).fillna("")
#     return list(df.columns), df.to_dict(orient="records")


# def _is_number(s: str) -> bool:
#     try: Decimal(s); return True
#     except: return False


# # ── Excel writer ──────────────────────────────────────────────────────────────

# def write_excel_output(output_rows, output_columns, audit, test_validation, out_path):
#     wb   = Workbook()
#     hf   = Font(name="Arial", bold=True, color="FFFFFF", size=10)
#     hfill= PatternFill("solid", fgColor="1F4E79")
#     cfill= PatternFill("solid", fgColor="E8F4FD")   # calculated
#     dfill= PatternFill("solid", fgColor="E8F5E9")   # db
#     pfill= PatternFill("solid", fgColor="FFF9C4")   # copy
#     ffill= PatternFill("solid", fgColor="FFCCCC")   # failed cell
#     pfass= PatternFill("solid", fgColor="CCFFCC")   # passed cell (validation)
#     thin = Side(style="thin", color="CCCCCC")
#     bdr  = Border(left=thin, right=thin, top=thin, bottom=thin)
#     ctr  = Alignment(horizontal="center", vertical="center", wrap_text=True)
#     lft  = Alignment(horizontal="left",   vertical="center")

#     rules = audit.get("interpreted_rules",[])
#     copy_cols = {r["output_col"] for r in rules if r.get("operation")=="copy"}
#     db_cols   = {r["output_col"] for r in rules if r.get("operation")=="db_lookup"}
#     calc_cols = {r["output_col"] for r in rules if r.get("operation") in ("multiply","subtract","divide","add_constant")}

#     # Build failed cells set for highlighting: {(row_idx, field)}
#     failed_cells = set()
#     if test_validation:
#         for d in test_validation.get("failures_only",[]):
#             failed_cells.add((d["row"], d["field"]))

#     # ── Sheet 1: Output data ───────────────────────────────────────────────────
#     ws = wb.active; ws.title = "Output_Data"
#     for ci, col in enumerate(output_columns, 1):
#         c = ws.cell(row=1, column=ci, value=col)
#         c.font=hf; c.fill=hfill; c.alignment=ctr; c.border=bdr
#         ws.column_dimensions[get_column_letter(ci)].width = max(14, len(col)+2)
#     ws.row_dimensions[1].height = 40
#     ws.freeze_panes = "A2"

#     for ri, row_data in enumerate(output_rows, 2):
#         for ci, col in enumerate(output_columns, 1):
#             val = row_data.get(col,"")
#             c = ws.cell(row=ri, column=ci, value=val)
#             c.border=bdr; c.alignment=lft; c.font=Font(name="Arial",size=9)
#             row_num = ri - 1  # 1-indexed data row
#             if (row_num, col) in failed_cells:
#                 c.fill = ffill   # red = validation failed
#             elif col in copy_cols:  c.fill = pfill
#             elif col in db_cols:    c.fill = dfill
#             elif col in calc_cols:  c.fill = cfill
#         ws.row_dimensions[ri].height = 18

#     # ── Sheet 2: Validation Report (Agent 10) ─────────────────────────────────
#     wv = wb.create_sheet("Validation_Report")
#     wv["A1"] = "Runtime Test Validation Report (Agent 10)"
#     wv["A1"].font = Font(bold=True, size=13, color="1F4E79")
#     wv.merge_cells("A1:G1")

#     if test_validation:
#         summary_rows = [
#             ("Status",          test_validation.get("status","?")),
#             ("Total cells",     str(test_validation.get("total",0))),
#             ("Passed",          str(test_validation.get("passed",0))),
#             ("Failed",          str(test_validation.get("failed",0))),
#             ("Skipped",         str(test_validation.get("skipped",0))),
#             ("Pass %",          f"{test_validation.get('pass_pct',0):.1f}%"),
#         ]
#         for i,(lbl,val) in enumerate(summary_rows, 3):
#             wv.cell(row=i,column=1,value=lbl).font = Font(bold=True,name="Arial",size=10)
#             wv.cell(row=i,column=2,value=val).font  = Font(name="Arial",size=10)

#         # Detailed results table
#         detail_hdr = ["Row","Field","Operation","Spec","Expected","Actual","Status","Reason"]
#         for ci,h in enumerate(detail_hdr,1):
#             c=wv.cell(row=12,column=ci,value=h)
#             c.font=hf; c.fill=hfill; c.alignment=ctr; c.border=bdr

#         for ri2, d in enumerate(test_validation.get("details",[])[:500], 13):
#             vals = [d["row"],d["field"],d["operation"],d["spec"],d["expected"],d["actual"],d["status"],d.get("reason","")]
#             for ci, v in enumerate(vals, 1):
#                 c = wv.cell(row=ri2,column=ci,value=v)
#                 c.font=Font(name="Arial",size=8); c.border=bdr; c.alignment=lft
#                 if d["status"]=="FAIL":  c.fill=ffill
#                 elif d["status"]=="PASS": c.fill=pfass
#         for ci,w in enumerate([6,20,14,40,16,16,8,30],1):
#             wv.column_dimensions[get_column_letter(ci)].width=w

#     # ── Sheet 3: Rule Summary ──────────────────────────────────────────────────
#     wr = wb.create_sheet("Rule_Summary")
#     hdrs=["Output Field","Operation","Operand A","Operand B / Constant","DB Key","Precision","Spec"]
#     for ci,h in enumerate(hdrs,1):
#         c=wr.cell(row=1,column=ci,value=h); c.font=hf; c.fill=hfill; c.alignment=ctr
#     spec_map = audit.get("spec_map",{})
#     for ri2, rule in enumerate(rules, 2):
#         col=rule.get("output_col",""); op=rule.get("operation","")
#         wr.cell(row=ri2,column=1,value=col)
#         wr.cell(row=ri2,column=2,value=op)
#         wr.cell(row=ri2,column=3,value=rule.get("operand_a","") or "")
#         wr.cell(row=ri2,column=4,value=str(rule.get("operand_b") or rule.get("constant") or ""))
#         wr.cell(row=ri2,column=5,value=rule.get("db_key","") or "")
#         wr.cell(row=ri2,column=6,value="4dp" if rule.get("precision") else "—")
#         wr.cell(row=ri2,column=7,value=spec_map.get(col,{}).get("spec",""))
#     for ci,w in enumerate([22,16,18,22,12,10,45],1):
#         wr.column_dimensions[get_column_letter(ci)].width=w

#     # ── Sheet 4: Audit ─────────────────────────────────────────────────────────
#     wa = wb.create_sheet("Audit_Report")
#     wa["A1"]="ETL Agent Audit Report"; wa["A1"].font=Font(bold=True,size=14,color="1F4E79")
#     wa.merge_cells("A1:D1")
#     tv = test_validation or {}
#     rows4=[
#         ("Run timestamp",     audit.get("timestamp","")),
#         ("LLM provider",      audit.get("llm_provider","")),
#         ("LLM model",         audit.get("llm_model","")),
#         ("Input file",        audit.get("input_file","")),
#         ("Rule mapping file", audit.get("rule_file","")),
#         ("Total rules",       str(audit.get("total_rules",""))),
#         ("Input rows",        str(audit.get("input_rows",""))),
#         ("Output columns",    str(audit.get("output_columns",""))),
#         ("Schema columns",    audit.get("schema_summary","")),
#         ("Drift detected",    str(audit.get("drift_detected",""))),
#         ("Drift summary",     audit.get("drift_summary","")),
#         ("Optimizations",     audit.get("optimization_summary","")),
#         ("Anomalies",         audit.get("anomaly_summary","")),
#         ("In-mem tests pass", str(audit.get("tests_passed",""))),
#         ("In-mem tests fail", str(audit.get("tests_failed",""))),
#         ("Excel validation",  tv.get("status","")),
#         ("Excel cells passed",str(tv.get("passed",""))),
#         ("Excel cells failed",str(tv.get("failed",""))),
#         ("Excel pass %",      f"{tv.get('pass_pct',0):.1f}%"),
#     ]
#     for i,(lbl,val) in enumerate(rows4,3):
#         wa.cell(row=i,column=1,value=lbl).font=Font(bold=True,name="Arial",size=10)
#         c=wa.cell(row=i,column=2,value=val); c.font=Font(name="Arial",size=10); c.alignment=Alignment(wrap_text=True)
#     wa.column_dimensions["A"].width=28; wa.column_dimensions["B"].width=65

#     # ── Sheet 5: Legend ────────────────────────────────────────────────────────
#     wl=wb.create_sheet("Legend")
#     wl["A1"]="Color Legend"; wl["A1"].font=Font(bold=True,size=12)
#     for i,(lbl,col) in enumerate([
#         ("Direct copy from input","FFF9C4"),
#         ("DB lookup value","E8F5E9"),
#         ("Calculated (BigDecimal)","E8F4FD"),
#         ("Validation PASSED","CCFFCC"),
#         ("Validation FAILED","FFCCCC"),
#     ],3):
#         wl.cell(row=i,column=1,value=lbl).font=Font(name="Arial",size=10)
#         wl.cell(row=i,column=2).fill=PatternFill("solid",fgColor=col)
#         wl.cell(row=i,column=2,value="  sample  ")
#     wl.column_dimensions["A"].width=35; wl.column_dimensions["B"].width=18

#     wb.save(out_path)
#     print(f"\n✅ Excel written → {out_path}")
#     print(f"   Sheets: {[s.title for s in wb.worksheets]}")
#     print(f"   Data: {len(output_rows)} rows × {len(output_columns)} cols")


# # ── Main pipeline ─────────────────────────────────────────────────────────────

# def run(
#     input_file:   str,
#     rule_file:    str,
#     out_path:     str,
#     provider:     str   = "claude",
#     model:        str | None = None,
#     fallback:     str | None = None,
#     fallback_model: str | None = None,
#     ollama_host:  str   = "http://localhost:11434",
# ) -> dict:

#     banner(f"INVESTMENT ETL — 10 AGENTS  |  provider={provider}  |  fallback={fallback or 'none'}")
#     ts    = datetime.now(timezone.utc).isoformat()
#     audit: dict = {"timestamp": ts, "input_file": input_file, "rule_file": rule_file}

#     # ── Build LLM router ──────────────────────────────────────────────────────
#     fb_chain = []
#     if fallback:
#         fb_defaults = {"claude":"claude-sonnet-4-20250514","gemini":"gemini-2.0-flash","ollama":"llama3.2"}
#         fb_chain = [(fallback, fallback_model or fb_defaults.get(fallback,""))]

#     router = LLMRouter(
#         provider=provider, model=model,
#         ollama_host=ollama_host,
#         fallback_chain=fb_chain,
#     )
#     print(f"\n[Router] Providers: {router.describe()}")
#     print(f"[Router] Active:    {router.active_provider}")
#     audit["llm_provider"] = router.active_provider
#     audit["llm_model"]    = router.describe()

#     # ── Load files ────────────────────────────────────────────────────────────
#     print(f"\n[Loader] Rule mapping : {rule_file}")
#     output_columns, raw_rules = read_rule_mapping(rule_file)
#     audit["total_rules"] = len(raw_rules)
#     audit["output_columns"] = len(output_columns)
#     print(f"[Loader] {len(raw_rules)} rules → {len(output_columns)} output columns")

#     print(f"[Loader] Input data   : {input_file}")
#     input_columns, input_rows = read_input_data(input_file)
#     audit["input_rows"] = len(input_rows)
#     print(f"[Loader] {len(input_rows)} rows, cols: {input_columns}")

#     # ── Agent 1: Schema Analyzer ──────────────────────────────────────────────
#     banner("AGENT 1 — Schema Analyzer")
#     schema = SchemaAnalyzerAgent(router).analyze(input_columns, input_rows)
#     audit["schema_summary"] = f"{len(schema.get('columns',[]))} columns classified"

#     # ── Agent 2: Rule Interpreter ─────────────────────────────────────────────
#     banner("AGENT 2 — Rule Interpreter")
#     interpreted = RuleInterpreterAgent(router).interpret(raw_rules, input_columns)
#     for i, rule in enumerate(interpreted):
#         if not rule.get("output_col") and i < len(raw_rules):
#             rule["output_col"] = raw_rules[i].get("output_col","")
#     audit["interpreted_rules"] = interpreted

#     # ── Agent 3: Arithmetic Precision Guard ───────────────────────────────────
#     banner("AGENT 3 — Arithmetic Precision Guard")
#     interpreted = ArithmeticPrecisionAgent(router).validate_and_route(interpreted)

#     # ── Agent 4: DB Mapping ───────────────────────────────────────────────────
#     banner("AGENT 4 — DB Mapping")
#     db_resolved = DBMappingAgent(router).resolve(interpreted, input_rows)

#     # ── Agent 5: Output Mapping ───────────────────────────────────────────────
#     banner("AGENT 5 — Output Mapping (Execution)")
#     output_rows = OutputMappingAgent(router).execute(interpreted, input_rows, db_resolved, output_columns)

#     # ── Agent 6: Drift Detection ──────────────────────────────────────────────
#     banner("AGENT 6 — Drift Detection")
#     drift = DriftDetectionAgent(router).detect(interpreted, output_rows, input_rows)
#     audit["drift_detected"] = drift.get("drift_detected", False)
#     audit["drift_summary"]  = drift.get("summary","")

#     # ── Agent 7: Rule Optimization ────────────────────────────────────────────
#     banner("AGENT 7 — Rule Optimization")
#     opt = RuleOptimizationAgent(router).optimize(interpreted)
#     audit["optimization_summary"] = opt.get("summary","")

#     # ── Agent 8: Test Generation (in-memory) ──────────────────────────────────
#     banner("AGENT 8 — Test Generation & In-Memory Run")
#     tg   = TestGenerationAgent(router)
#     tcs  = tg.generate(interpreted, input_rows[0] if input_rows else {}, input_columns)
#     tres = tg.run_tests(tcs, output_rows, input_rows)
#     audit["tests_passed"] = tres["passed"]
#     audit["tests_failed"] = tres["failed"]

#     # ── Agent 9: Anomaly Detection ────────────────────────────────────────────
#     banner("AGENT 9 — Anomaly Detection")
#     anom = AnomalyDetectionAgent(router).detect(output_rows, interpreted)
#     audit["anomaly_count"]   = len(anom.get("anomalies",[]))
#     audit["anomaly_summary"] = anom.get("summary","")

#     # ── Write Excel ───────────────────────────────────────────────────────────
#     banner("WRITING EXCEL OUTPUT (pre-validation draft)")
#     Path(out_path).parent.mkdir(parents=True, exist_ok=True)
#     write_excel_output(output_rows, output_columns, audit, None, out_path)

#     # ── Agent 10: Runtime Test Validator ──────────────────────────────────────
#     banner("AGENT 10 — Runtime Test Validator (Excel cell-by-cell)")
#     rtv = RuntimeTestValidatorAgent(router)
#     expected_rows, spec_map = rtv.compute_expected(interpreted, input_rows, db_resolved, output_columns)
#     audit["spec_map"] = spec_map
#     validation = rtv.validate_excel(out_path, expected_rows, spec_map, output_columns, interpreted)
#     audit["validation"] = validation

#     # ── Rewrite Excel with validation highlights ───────────────────────────────
#     banner("REWRITING EXCEL WITH VALIDATION HIGHLIGHTS")
#     write_excel_output(output_rows, output_columns, audit, validation, out_path)

#     # ── Final summary ─────────────────────────────────────────────────────────
#     banner("PIPELINE COMPLETE")
#     tv = validation
#     print(f"  LLM provider        : {router.describe()}")
#     print(f"  Input rows          : {len(input_rows)}")
#     print(f"  Output columns      : {len(output_columns)}")
#     print(f"  Rules executed      : {len(interpreted)}")
#     print(f"  DB lookups          : {sum(1 for r in interpreted if r.get('operation')=='db_lookup')}")
#     print(f"  Arithmetic ops      : {sum(1 for r in interpreted if r.get('decimal_engine'))}")
#     print(f"  Drift detected      : {audit['drift_detected']}")
#     print(f"  Anomalies           : {audit['anomaly_count']}")
#     print(f"  In-memory tests     : {audit['tests_passed']}/{tres['total']} passed")
#     print(f"  Excel validation    : {tv['status']} — {tv['passed']}/{tv['total']} cells ({tv['pass_pct']}%)")
#     if tv.get("field_failures"):
#         print(f"  Failed fields       : {dict(list(tv['field_failures'].items())[:5])}")
#     print(f"  Output file         : {out_path}")

#     return audit


# # ── CLI ───────────────────────────────────────────────────────────────────────

# def _cli():
#     p = argparse.ArgumentParser(description="Investment ETL — 10 AI Agents")
#     p.add_argument("--input",   required=True, help="Input data Excel file")
#     p.add_argument("--rules",   required=True, help="Rule mapping Excel file")
#     p.add_argument("--out",     default="output/Investment_Output.xlsx", help="Output Excel path")
#     p.add_argument("--provider",default="claude", choices=["claude","gemini","ollama"], help="Primary LLM provider")
#     p.add_argument("--model",   default=None, help="Model name (optional)")
#     p.add_argument("--fallback",default=None, choices=["claude","gemini","ollama",""], help="Fallback provider")
#     p.add_argument("--fallback-model", default=None, help="Fallback model name")
#     p.add_argument("--ollama-host", default="http://localhost:11434", help="Ollama server URL")
#     args = p.parse_args()

#     run(
#         input_file     = args.input,
#         rule_file      = args.rules,
#         out_path       = args.out,
#         provider       = args.provider,
#         model          = args.model,
#         fallback       = args.fallback or None,
#         fallback_model = args.fallback_model,
#         ollama_host    = args.ollama_host,
#     )


# if __name__ == "__main__":
#     if len(sys.argv) > 1:
#         _cli()
#     else:
#         # Default: run with sample files
#         run(
#             input_file = "/mnt/user-data/uploads/Investment_Sample_Data__1_.xlsx",
#             rule_file  = "/mnt/user-data/uploads/Rule_Mapping_92_English.xlsx",
#             out_path   = "/mnt/user-data/outputs/Investment_Output_v2.xlsx",
#             provider   = "claude",
#         )
