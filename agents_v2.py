# """
# agents.py  (v2)
# ===============
# 10 AI Agents — provider-agnostic (Claude / Gemini / Ollama).
# All arithmetic delegated to arithmetic_engine.py (BigDecimal, no AI math).
# """
# from __future__ import annotations
# import json, re, sys, os
# from decimal import Decimal, ROUND_HALF_UP
# from typing import Any

# sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
# from engine.arithmetic_engine import compute_multiply, compute_subtract, compute_divide, compute_add_constant, to_decimal
# from db.mock_db import db_lookup


# class BaseAgent:
#     NAME = "BaseAgent"
#     def __init__(self, router): self.router = router
#     def _llm(self, system, user, max_tokens=3000): return self.router.call(system, user, max_tokens)
#     def _llm_json(self, system, user, max_tokens=3000): return self.router.call_json(system, user, max_tokens)
#     def _log(self, msg): print(f"[{self.NAME}] {msg}")


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 1: Schema Analyzer
# # ══════════════════════════════════════════════════════════════════════════════
# class SchemaAnalyzerAgent(BaseAgent):
#     NAME = "SchemaAnalyzerAgent"

#     def analyze(self, columns: list[str], sample_rows: list[dict]) -> dict:
#         self._log(f"Analyzing {len(columns)} columns via [{self.router.active_provider}]...")
#         system = """You are a financial data schema expert.
# Analyze column names and sample rows from ANY financial Excel file.
# For each column identify: semantic_type (price|identifier|name|rate|quantity|date|text|unknown),
# data_type (string|decimal|integer|date|boolean), nullable (true|false), description (one sentence).
# Return ONLY JSON: {"columns":[{"name":"...","semantic_type":"...","data_type":"...","nullable":true,"description":"..."}]}"""
#         user = f"Columns: {columns}\nSample rows (up to 3): {json.dumps(sample_rows[:3], default=str)}"
#         result = self._llm_json(system, user)
#         if not result or "columns" not in result:
#             self._log("LLM unavailable — heuristic fallback")
#             result = self._fallback(columns, sample_rows)
#         self._log(f"✅ {len(result.get('columns',[]))} columns classified")
#         return result

#     def _fallback(self, columns, sample_rows):
#         type_hints = {"price":"decimal","nominal":"decimal","brokerage":"decimal",
#                       "quantity":"decimal","rate":"decimal","amount":"decimal",
#                       "isin":"string","broker":"string","scheme":"string","name":"string"}
#         sem_hints  = {"price":"price","nominal":"value","brokerage":"rate","quantity":"quantity",
#                       "isin":"identifier","broker":"name","scheme":"name","name":"name"}
#         cols = []
#         for col in columns:
#             cl = col.lower()
#             dt = next((v for k,v in type_hints.items() if k in cl), "string")
#             st = next((v for k,v in sem_hints.items()  if k in cl), "text")
#             if sample_rows:
#                 try: Decimal(str(sample_rows[0].get(col,""))); dt="decimal"
#                 except: pass
#             cols.append({"name":col,"semantic_type":st,"data_type":dt,"nullable":True,"description":f"Input column '{col}'"})
#         return {"columns": cols}


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 2: Rule Interpreter
# # ══════════════════════════════════════════════════════════════════════════════
# class RuleInterpreterAgent(BaseAgent):
#     NAME = "RuleInterpreterAgent"

#     def interpret(self, rules: list[dict], input_columns: list[str]) -> list[dict]:
#         self._log(f"Interpreting {len(rules)} rules via [{self.router.active_provider}]...")
#         system = f"""You are an ETL rule interpreter for financial data.
# Available input columns: {input_columns}
# Convert each English business rule to a structured operation.
# Operations: copy | multiply | subtract | divide | add_constant | db_lookup
# For each rule output a JSON object:
# {{"output_col":"<field>","operation":"<op>","operand_a":"<col or null>","operand_b":"<col or null>","constant":<num or null>,"db_key":"<KEY_N or null>","reasoning":"<one line>"}}
# - "Copy X from input" → copy, operand_a = exact input column name matching X
# - "Multiply A and B"  → multiply, operand_a=A, operand_b=B
# - "Subtract B from A" → subtract, operand_a=A, operand_b=B  
# - "Divide A by B"     → divide, operand_a=A, operand_b=B
# - "Add constant N to X" → add_constant, operand_a=X, constant=N (numeric)
# - "Fetch from database using ISIN and key KEY_N" → db_lookup, db_key="KEY_N"
# Return ONLY a JSON array — one object per rule, in same order."""

#         all_out: list[dict] = []
#         for i in range(0, len(rules), 30):
#             batch  = rules[i:i+30]
#             result = self._llm_json(system, f"Rules:\n{json.dumps(batch, indent=2)}", max_tokens=4096)
#             if isinstance(result, list) and result:
#                 all_out.extend(result)
#             else:
#                 self._log(f"Fallback for batch {i//30+1}")
#                 all_out.extend(self._fallback(batch))

#         # Ensure output_col alignment
#         for idx, rule in enumerate(all_out):
#             if not rule.get("output_col") and idx < len(rules):
#                 rule["output_col"] = rules[idx].get("output_col", f"field_{idx+1}")
#         self._log(f"✅ {len(all_out)} rules interpreted")
#         return all_out

#     def _fallback(self, rules):
#         out = []
#         for r in rules:
#             txt = r.get("business_rule","").lower()
#             oc  = r.get("output_col","")
#             ic  = str(r.get("input_columns","")).split(",")
#             ic  = [c.strip() for c in ic]
#             m_db  = re.search(r"key\s+(key_\d+)", txt, re.I)
#             m_con = re.search(r"constant value\s+(\d+(?:\.\d+)?)", txt)
#             if m_db:
#                 op = {"operation":"db_lookup","operand_a":None,"operand_b":None,"constant":None,"db_key":m_db.group(1).upper()}
#             elif "multiply" in txt:
#                 op = {"operation":"multiply","operand_a":ic[0] if ic else None,"operand_b":ic[1] if len(ic)>1 else None,"constant":None,"db_key":None}
#             elif m_con and "add" in txt:
#                 op = {"operation":"add_constant","operand_a":ic[0] if ic else None,"operand_b":None,"constant":float(m_con.group(1)),"db_key":None}
#             elif "subtract" in txt or "net price" in txt:
#                 op = {"operation":"subtract","operand_a":ic[0] if ic else None,"operand_b":ic[1] if len(ic)>1 else None,"constant":None,"db_key":None}
#             elif "divide" in txt:
#                 op = {"operation":"divide","operand_a":ic[0] if ic else None,"operand_b":ic[1] if len(ic)>1 else None,"constant":None,"db_key":None}
#             else:
#                 op = {"operation":"copy","operand_a":ic[0] if ic else None,"operand_b":None,"constant":None,"db_key":None}
#             out.append({"output_col":oc,"reasoning":"regex fallback",**op})
#         return out


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 3: Arithmetic Precision Guard — deterministic
# # ══════════════════════════════════════════════════════════════════════════════
# class ArithmeticPrecisionAgent(BaseAgent):
#     NAME = "ArithmeticPrecisionAgent"
#     ARITH = {"multiply","subtract","divide","add_constant"}

#     def validate_and_route(self, rules: list[dict]) -> list[dict]:
#         self._log(f"Validating {len(rules)} rules for BigDecimal compliance...")
#         issues, cnt = [], 0
#         for rule in rules:
#             op = rule.get("operation","")
#             if op in self.ARITH:
#                 rule.update({"precision":4,"decimal_engine":True,"float_prohibited":True})
#                 cnt += 1
#                 if op != "add_constant" and not rule.get("operand_b"):
#                     issues.append(f"⚠ {rule['output_col']}: '{op}' missing operand_b")
#                 if op == "add_constant" and rule.get("constant") is None:
#                     issues.append(f"⚠ {rule['output_col']}: missing constant value")
#         for iss in issues: self._log(iss)
#         self._log(f"✅ {cnt} ops → Decimal engine. Issues={len(issues)}")
#         return rules


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 4: DB Mapping — deterministic
# # ══════════════════════════════════════════════════════════════════════════════
# class DBMappingAgent(BaseAgent):
#     NAME = "DBMappingAgent"

#     def resolve(self, rules: list[dict], input_rows: list[dict], isin_column: str = "ISIN") -> dict:
#         db_rules = [r for r in rules if r.get("operation") == "db_lookup"]
#         self._log(f"Resolving {len(db_rules)} DB fields × {len(input_rows)} rows...")
#         resolved: dict[tuple,str] = {}
#         for ri, row in enumerate(input_rows):
#             isin = ""
#             for cand in [isin_column, "ISIN", "isin"]:
#                 if cand in row and row[cand]:
#                     isin = str(row[cand]).strip(); break
#             if not isin:
#                 for v in row.values():
#                     if re.match(r"INF\w+", str(v)): isin = str(v).strip(); break
#             for rule in db_rules:
#                 resolved[(ri, rule["output_col"])] = db_lookup(isin, rule.get("db_key",""))
#         found = sum(1 for v in resolved.values() if v != "N/A")
#         self._log(f"✅ {found}/{len(resolved)} DB values resolved")
#         return resolved


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 5: Output Mapping — deterministic execution
# # ══════════════════════════════════════════════════════════════════════════════
# class OutputMappingAgent(BaseAgent):
#     NAME = "OutputMappingAgent"

#     def execute(self, rules, input_rows, db_resolved, output_columns) -> list[dict]:
#         self._log(f"Executing {len(rules)} rules × {len(input_rows)} rows...")
#         output_rows = []
#         for ri, row in enumerate(input_rows):
#             out: dict[str,Any] = {}
#             for rule in rules:
#                 col, op = rule.get("output_col",""), rule.get("operation","")
#                 oa, ob, const = rule.get("operand_a"), rule.get("operand_b"), rule.get("constant")
#                 va = row.get(oa,"") if oa else ""
#                 vb = row.get(ob,"") if ob else ""
#                 if   op == "copy":          out[col] = str(row.get(oa,"")).strip()
#                 elif op == "multiply":      out[col] = compute_multiply(va, vb)
#                 elif op == "subtract":      out[col] = compute_subtract(va, vb)
#                 elif op == "divide":        out[col] = compute_divide(va, vb)
#                 elif op == "add_constant":  out[col] = compute_add_constant(va, const)
#                 elif op == "db_lookup":     out[col] = db_resolved.get((ri, col), "N/A")
#                 else:                       out[col] = ""
#             for col in output_columns: out.setdefault(col, "")
#             output_rows.append(out)
#         self._log(f"✅ {len(output_rows)} rows × {len(output_columns)} cols")
#         return output_rows


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 6: Drift Detection — NLP
# # ══════════════════════════════════════════════════════════════════════════════
# class DriftDetectionAgent(BaseAgent):
#     NAME = "DriftDetectionAgent"

#     def detect(self, rules, output_rows, input_rows) -> dict:
#         self._log(f"Drift detection via [{self.router.active_provider}]...")
#         samples = [{"row":i+1,"input":inp,"output_sample":{k:out[k] for k in list(out)[:12]}}
#                    for i,(inp,out) in enumerate(zip(input_rows[:3],output_rows[:3]))]
#         system = """You are a data drift detection specialist.
# Check input→output samples for systematic errors: wrong field used, wrong sign, wrong scale, wrong constant.
# Return JSON: {"drift_detected":false,"issues":[{"field":"...","issue":"...","severity":"high|medium|low"}],"summary":"..."}"""
#         result = self._llm_json(system, f"Rules (first 15):\n{json.dumps(rules[:15],indent=2)}\n\nSamples:\n{json.dumps(samples,indent=2)}")
#         if not result: result = {"drift_detected":False,"issues":[],"summary":"No drift (fallback)."}
#         self._log(f"✅ drift={'YES ⚠' if result.get('drift_detected') else 'none'}, issues={len(result.get('issues',[]))}")
#         return result


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 7: Rule Optimization — NLP
# # ══════════════════════════════════════════════════════════════════════════════
# class RuleOptimizationAgent(BaseAgent):
#     NAME = "RuleOptimizationAgent"

#     def optimize(self, rules) -> dict:
#         self._log(f"Optimizing {len(rules)} rules via [{self.router.active_provider}]...")
#         dist = {}
#         for r in rules: dist[r.get("operation","?")] = dist.get(r.get("operation","?"),0)+1
#         system = """ETL optimization expert. Suggest batching, caching, de-duplication opportunities.
# Return JSON: {"optimizations":[{"type":"...","description":"...","impact":"high|medium|low","affected_fields":[...]}],"summary":"..."}"""
#         result = self._llm_json(system, f"Op distribution: {dist}\nSample rules: {json.dumps(rules[:10],indent=2)}")
#         if not result:
#             db_f = [r["output_col"] for r in rules if r.get("operation")=="db_lookup"]
#             result = {"optimizations":[
#                 {"type":"batch_db_lookups","description":f"{len(db_f)} DB lookups → batch per ISIN","impact":"high","affected_fields":db_f},
#                 {"type":"template_arithmetic","description":"Repeating arithmetic groups → template","impact":"medium","affected_fields":[]},
#             ],"summary":f"{dist}"}
#         self._log(f"✅ {len(result.get('optimizations',[]))} optimizations")
#         return result


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 8: Test Generation — NLP generates, deterministic runs
# # ══════════════════════════════════════════════════════════════════════════════
# class TestGenerationAgent(BaseAgent):
#     NAME = "TestGenerationAgent"

#     def generate(self, rules, sample_input, input_columns) -> list[dict]:
#         self._log(f"Generating test cases via [{self.router.active_provider}]...")
#         system = f"""You are a financial ETL QA engineer.
# Input columns: {input_columns}
# For each rule create a happy-path test AND an edge-case test (zero, very large number, empty string).
# Return JSON array:
# [{{"rule_field":"...","operation":"...","test_name":"...","inputs":{{}},"expected_formula":"human readable e.g. Price × Nominal","edge_case":true/false}}]"""
#         result = self._llm_json(system, f"Rules:\n{json.dumps(rules[:20],indent=2)}\nSample input:\n{json.dumps(sample_input,default=str)}", max_tokens=4096)
#         if not result or not isinstance(result, list): result = self._fallback(rules, sample_input)
#         self._log(f"✅ {len(result)} test cases generated")
#         return result

#     def _fallback(self, rules, sample):
#         return [{"rule_field":r["output_col"],"operation":r.get("operation",""),
#                  "test_name":f"happy_{r['output_col']}","inputs":sample,
#                  "expected_formula":f"{r.get('operation')} on {r.get('operand_a')}","edge_case":False}
#                 for r in rules[:12]]

#     def run_tests(self, test_cases, output_rows, input_rows) -> dict:
#         self._log(f"Running {len(test_cases)} in-memory tests...")
#         passed = failed = 0
#         details = []
#         arith = {"multiply","subtract","divide","add_constant"}
#         for tc in test_cases:
#             field, op = tc.get("rule_field",""), tc.get("operation","")
#             for ri, row in enumerate(output_rows):
#                 actual = row.get(field, None)
#                 if actual is None:
#                     failed += 1
#                     details.append({"test":tc["test_name"],"row":ri+1,"status":"FAIL","reason":f"'{field}' missing"})
#                     continue
#                 if op in arith:
#                     try:
#                         Decimal(str(actual)); passed += 1
#                         details.append({"test":tc["test_name"],"row":ri+1,"status":"PASS","actual":str(actual)})
#                     except:
#                         failed += 1
#                         details.append({"test":tc["test_name"],"row":ri+1,"status":"FAIL","reason":f"'{actual}' not decimal"})
#                 else:
#                     passed += 1
#                     details.append({"test":tc["test_name"],"row":ri+1,"status":"PASS","actual":str(actual)})
#         self._log(f"✅ {passed}/{passed+failed} passed")
#         return {"passed":passed,"failed":failed,"total":passed+failed,"details":details[:40]}


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 9: Anomaly Detection — NLP
# # ══════════════════════════════════════════════════════════════════════════════
# class AnomalyDetectionAgent(BaseAgent):
#     NAME = "AnomalyDetectionAgent"

#     def detect(self, output_rows, rules) -> dict:
#         self._log(f"Anomaly scan via [{self.router.active_provider}]...")
#         stats: dict[str,list] = {}
#         for row in output_rows:
#             for k,v in row.items():
#                 if str(v) in ("N/A","","None"): continue
#                 try: stats.setdefault(k,[]).append(float(Decimal(str(v))))
#                 except: pass
#         summary = {k:{"min":min(v),"max":max(v),"mean":round(sum(v)/len(v),6),"zeros":v.count(0.0),"count":len(v)}
#                    for k,v in stats.items() if v}
#         system = """Financial anomaly detection expert.
# Flag: all-zero fields, extreme outliers (>10x mean), no-variation fields.
# Return JSON: {"anomalies":[{"field":"...","type":"...","detail":"...","severity":"high|medium|low"}],"clean_fields":<int>,"summary":"..."}"""
#         result = self._llm_json(system, f"Stats:\n{json.dumps(summary,indent=2)}\nRows: {len(output_rows)}")
#         if not result:
#             anoms = [{"field":k,"type":"all_zeros","detail":"All values 0","severity":"high"}
#                      for k,s in summary.items() if s["zeros"]==s["count"]>0]
#             result = {"anomalies":anoms,"clean_fields":len(summary)-len(anoms),"summary":f"{len(anoms)} anomalies."}
#         self._log(f"✅ {len(result.get('anomalies',[]))} anomalies")
#         return result


# # ══════════════════════════════════════════════════════════════════════════════
# # AGENT 10: Runtime Test Validator
# # Computes expected values at runtime → reads actual Excel → validates cell-by-cell
# # ══════════════════════════════════════════════════════════════════════════════
# class RuntimeTestValidatorAgent(BaseAgent):
#     NAME = "RuntimeTestValidatorAgent"

#     # ── Compute expected values deterministically ─────────────────────────────
#     def compute_expected(self, rules, input_rows, db_resolved, output_columns) -> tuple[list[dict], dict]:
#         self._log("Computing expected values deterministically...")
#         expected_rows = []
#         for ri, row in enumerate(input_rows):
#             exp: dict[str,Any] = {}
#             for rule in rules:
#                 col, op = rule.get("output_col",""), rule.get("operation","")
#                 oa, ob, const = rule.get("operand_a"), rule.get("operand_b"), rule.get("constant")
#                 va = row.get(oa,"") if oa else ""
#                 vb = row.get(ob,"") if ob else ""
#                 if   op == "copy":          exp[col] = str(row.get(oa,"")).strip()
#                 elif op == "multiply":      exp[col] = compute_multiply(va, vb)
#                 elif op == "subtract":      exp[col] = compute_subtract(va, vb)
#                 elif op == "divide":        exp[col] = compute_divide(va, vb)
#                 elif op == "add_constant":  exp[col] = compute_add_constant(va, const)
#                 elif op == "db_lookup":     exp[col] = db_resolved.get((ri, col), "N/A")
#                 else:                       exp[col] = ""
#             expected_rows.append(exp)

#         # LLM-generated test specs (descriptive)
#         self._log(f"Generating test specs via [{self.router.active_provider}]...")
#         system = """You are a QA engineer writing test specifications.
# For each rule write a clear validation spec, e.g. "field8 = Price × Nominal (BigDecimal 4dp)".
# Return JSON array: [{"field":"...","spec":"...","category":"arithmetic|copy|db_lookup|other"}]"""
#         sample_exp = {k:v for k,v in expected_rows[0].items() if k in output_columns[:15]} if expected_rows else {}
#         specs_raw = self._llm_json(system,
#             f"Rules:\n{json.dumps(rules[:25],indent=2)}\nSample expected (row1):\n{json.dumps(sample_exp)}",
#             max_tokens=3000)
#         specs_raw = specs_raw if isinstance(specs_raw, list) else []
#         spec_map = {s["field"]: s for s in specs_raw}

#         # Fallback specs for any missing
#         for rule in rules:
#             col = rule.get("output_col","")
#             if col not in spec_map:
#                 op = rule.get("operation","")
#                 a, b, c, k = rule.get("operand_a","?"), rule.get("operand_b","?"), rule.get("constant","?"), rule.get("db_key","?")
#                 specs = {"copy":f"Copy {a} from input","multiply":f"{a} × {b} (4dp)",
#                          "subtract":f"{a} − {b} (4dp)","divide":f"{a} ÷ {b} (4dp)",
#                          "add_constant":f"{a} + {c} (4dp)","db_lookup":f"DB(ISIN→{k})"}
#                 spec_map[col] = {"field":col,"spec":specs.get(op,op),"category":op if op in("copy","db_lookup") else "arithmetic"}

#         self._log(f"✅ {len(expected_rows)} expected rows, {len(spec_map)} specs ready")
#         return expected_rows, spec_map

#     # ── Read actual Excel and validate every cell ─────────────────────────────
#     def validate_excel(self, excel_path, expected_rows, spec_map, output_columns, rules) -> dict:
#         import openpyxl
#         self._log(f"Validating '{excel_path}' cell-by-cell ({len(expected_rows)} rows × {len(output_columns)} cols)...")

#         try:
#             wb = openpyxl.load_workbook(excel_path, data_only=True)
#             ws = wb.active
#         except Exception as e:
#             return {"status":"ERROR","error":str(e),"passed":0,"failed":0,"total":0,"details":[]}

#         headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column+1)]
#         col_idx = {h:i+1 for i,h in enumerate(headers) if h}

#         rule_map = {r.get("output_col",""): r for r in rules}
#         results = []
#         passed = failed = skipped = 0

#         for ri, exp_row in enumerate(expected_rows):
#             excel_row = ri + 2
#             for col in output_columns:
#                 if col not in col_idx:
#                     skipped += 1; continue
#                 raw    = ws.cell(row=excel_row, column=col_idx[col]).value
#                 actual = str(raw).strip() if raw is not None else ""
#                 exp    = str(exp_row.get(col,"")).strip()
#                 rule   = rule_map.get(col, {})
#                 op     = rule.get("operation","")
#                 spec   = spec_map.get(col,{}).get("spec","")

#                 status, reason = self._compare(actual, exp, op)
#                 if status == "PASS": passed += 1
#                 else:                failed += 1

#                 results.append({"row":ri+1,"field":col,"operation":op,"spec":spec,
#                                  "expected":exp,"actual":actual,"status":status,"reason":reason})

#         total = passed + failed
#         pct   = round(100*passed/total, 1) if total else 0.0
#         field_fails = {}
#         for r in results:
#             if r["status"]=="FAIL":
#                 field_fails[r["field"]] = field_fails.get(r["field"],0)+1

#         self._log(f"✅ {passed}/{total} passed ({pct}%), {failed} failed, {skipped} skipped")
#         return {
#             "status":         "PASS" if failed==0 else "FAIL",
#             "passed":         passed, "failed":failed, "skipped":skipped,
#             "total":          total,  "pass_pct":pct,
#             "field_failures": field_fails,
#             "details":        results,
#             "failures_only":  [r for r in results if r["status"]=="FAIL"],
#         }

#     def _compare(self, actual: str, expected: str, op: str) -> tuple[str,str]:
#         if actual == expected: return "PASS", ""
#         try:
#             diff = abs(to_decimal(actual) - to_decimal(expected))
#             if diff <= Decimal("0.00005"): return "PASS", ""
#             return "FAIL", f"expected={expected}, actual={actual}, diff={diff}"
#         except: pass
#         if actual.strip() == expected.strip(): return "PASS", ""
#         return "FAIL", f"expected='{expected}' actual='{actual}'"
