"""Herramientas de análisis de código deterministas y locales.

Permiten a los agentes de programación "interactuar" con el código que el
usuario pega sin ejecutarlo nunca: solo análisis estático (AST de Python y
heurísticas por expresiones regulares). Cumplen el modelo de seguridad de la
plataforma: sin red, sin subprocesos, sin tocar el sistema de archivos.

- analyze_code_structure: estructura (funciones, clases, imports, complejidad).
- review_code_quality:    hallazgos de calidad/mantenibilidad heurísticos.
- scan_code_security:     patrones de riesgo de seguridad (SAST ligero, CWE).
- generate_test_skeleton: esqueletos de tests (pytest) a partir de funciones.
- extract_code_todos:     marcadores TODO/FIXME/HACK/XXX/BUG con su línea.
"""
from __future__ import annotations

import ast
import re
from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import BaseTool, ToolContext, ToolError

_MAX_CODE_CHARS = 100000

# ---------------------------------------------------------------------------
# Detección de lenguaje (heurística por marcadores sintácticos)
# ---------------------------------------------------------------------------

_LANGUAGE_HINTS: list[tuple[str, list[str]]] = [
    ("python", ["def ", "import ", "self.", "elif ", "lambda ", "__init__"]),
    ("javascript", ["function ", "const ", "let ", "=>", "console.log", "require(", "export "]),
    ("typescript", ["interface ", ": string", ": number", "implements ", "declare "]),
    ("java", ["public class", "private ", "void ", "System.out", "import java"]),
    ("go", ["package ", "func ", "fmt.", ":= ", "chan "]),
    ("csharp", ["using System", "namespace ", "public class", "Console.Write"]),
    ("php", ["<?php", "$", "echo ", "->"]),
    ("ruby", ["def ", "end\n", "puts ", "require ", "attr_"]),
    ("rust", ["fn ", "let mut", "impl ", "pub fn", "->"]),
    ("sql", ["select ", "insert into", "create table", "update ", "where "]),
]


def detect_language(code: str, declared: str | None = None) -> str:
    if declared and declared.lower() != "auto":
        return declared.lower()
    lowered = code.lower()
    best, best_score = "desconocido", 0
    for language, markers in _LANGUAGE_HINTS:
        score = sum(1 for marker in markers if marker.lower() in lowered)
        if score > best_score:
            best, best_score = language, score
    return best if best_score else "desconocido"


def _line_metrics(code: str) -> dict[str, Any]:
    lines = code.splitlines()
    non_empty = [ln for ln in lines if ln.strip()]
    comment_lines = sum(
        1 for ln in lines if ln.strip().startswith(("#", "//", "*", "/*", "--"))
    )
    longest = max((len(ln) for ln in lines), default=0)
    return {
        "total_lines": len(lines),
        "code_lines": len(non_empty),
        "blank_lines": len(lines) - len(non_empty),
        "comment_lines": comment_lines,
        "longest_line_chars": longest,
    }


# ---------------------------------------------------------------------------
# Complejidad ciclomática aproximada (solo Python, vía AST)
# ---------------------------------------------------------------------------

_BRANCHING_NODES = (
    ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try,
    ast.With, ast.AsyncWith, ast.ExceptHandler, ast.BoolOp,
    ast.comprehension, ast.IfExp,
)


def _cyclomatic_complexity(node: ast.AST) -> int:
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, _BRANCHING_NODES):
            complexity += 1
    return complexity


def _max_depth(node: ast.AST, current: int = 0) -> int:
    nesting = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)
    depth = current
    for child in ast.iter_child_nodes(node):
        child_depth = _max_depth(child, current + 1 if isinstance(child, nesting) else current)
        depth = max(depth, child_depth)
    return depth


# ---------------------------------------------------------------------------
# analyze_code_structure
# ---------------------------------------------------------------------------


class AnalyzeCodeStructureInput(BaseModel):
    code: str = Field(min_length=1, max_length=_MAX_CODE_CHARS, description="Código fuente a analizar")
    language: str | None = Field(default=None, description="Lenguaje o 'auto' para detectarlo")


class AnalyzeCodeStructureTool(BaseTool):
    name = "analyze_code_structure"
    category = "programming"
    description = (
        "Analiza la estructura del código (funciones, clases, imports, complejidad "
        "ciclomática y métricas de líneas). En Python usa el AST; en otros lenguajes, "
        "heurísticas. Nunca ejecuta el código."
    )
    input_schema = AnalyzeCodeStructureInput
    timeout_seconds = 10

    def execute(self, payload: AnalyzeCodeStructureInput, ctx: ToolContext) -> dict[str, Any]:
        code = payload.code
        language = detect_language(code, payload.language)
        metrics = _line_metrics(code)

        if language == "python":
            structure = self._analyze_python(code)
        else:
            structure = self._analyze_generic(code, language)

        return {"language": language, "metrics": metrics, **structure}

    def _analyze_python(self, code: str) -> dict[str, Any]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {
                "parse_ok": False,
                "syntax_error": f"línea {exc.lineno}: {exc.msg}",
                "functions": [],
                "classes": [],
                "imports": [],
                "note": "El código Python no compila sintácticamente; análisis limitado.",
            }

        functions: list[dict[str, Any]] = []
        classes: list[dict[str, Any]] = []
        imports: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "args": len(node.args.args) + len(node.args.kwonlyargs),
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "has_docstring": ast.get_docstring(node) is not None,
                        "complexity": _cyclomatic_complexity(node),
                        "decorators": [ast.unparse(d) for d in node.decorator_list][:5],
                    }
                )
            elif isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in node.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                classes.append(
                    {
                        "name": node.name,
                        "line": node.lineno,
                        "methods": methods,
                        "method_count": len(methods),
                        "has_docstring": ast.get_docstring(node) is not None,
                        "bases": [ast.unparse(b) for b in node.bases][:5],
                    }
                )
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.extend(f"{module}.{alias.name}" if module else alias.name for alias in node.names)

        complexities = [f["complexity"] for f in functions]
        return {
            "parse_ok": True,
            "functions": sorted(functions, key=lambda f: -f["complexity"])[:50],
            "classes": classes[:50],
            "imports": sorted(set(imports))[:50],
            "function_count": len(functions),
            "class_count": len(classes),
            "max_complexity": max(complexities, default=0),
            "max_nesting_depth": _max_depth(tree),
            "undocumented_functions": [f["name"] for f in functions if not f["has_docstring"]][:30],
        }

    def _analyze_generic(self, code: str, language: str) -> dict[str, Any]:
        func_pattern = re.compile(
            r"(?:function\s+(\w+)|(?:func|fn|def)\s+(\w+)|(\w+)\s*[:=]\s*(?:async\s*)?\([^)]*\)\s*=>)"
        )
        class_pattern = re.compile(r"(?:class|interface|struct|impl)\s+(\w+)")
        functions = []
        for index, line in enumerate(code.splitlines(), start=1):
            match = func_pattern.search(line)
            if match:
                name = next((g for g in match.groups() if g), "anónima")
                functions.append({"name": name, "line": index})
        classes = sorted({m.group(1) for m in class_pattern.finditer(code)})
        return {
            "parse_ok": True,
            "functions": functions[:50],
            "classes": classes[:50],
            "imports": [],
            "function_count": len(functions),
            "class_count": len(classes),
            "note": f"Análisis heurístico para '{language}' (sin AST): cifras aproximadas.",
        }


# ---------------------------------------------------------------------------
# review_code_quality
# ---------------------------------------------------------------------------


class ReviewCodeQualityInput(BaseModel):
    code: str = Field(min_length=1, max_length=_MAX_CODE_CHARS)
    language: str | None = Field(default=None)
    max_line_length: int = Field(default=120, ge=60, le=300)
    max_function_lines: int = Field(default=50, ge=10, le=300)


class ReviewCodeQualityTool(BaseTool):
    name = "review_code_quality"
    category = "programming"
    description = (
        "Revisión heurística de calidad y mantenibilidad: funciones largas, exceso "
        "de argumentos, falta de docstrings, except genéricos, líneas largas, prints "
        "olvidados y marcadores TODO. Devuelve hallazgos con línea y severidad."
    )
    input_schema = ReviewCodeQualityInput
    timeout_seconds = 10

    def execute(self, payload: ReviewCodeQualityInput, ctx: ToolContext) -> dict[str, Any]:
        code = payload.code
        language = detect_language(code, payload.language)
        findings: list[dict[str, Any]] = []
        lines = code.splitlines()

        for index, line in enumerate(lines, start=1):
            if len(line) > payload.max_line_length:
                findings.append(self._finding(index, "info", "linea_larga",
                    f"Línea de {len(line)} caracteres (máx. {payload.max_line_length})."))
            if re.search(r"\bprint\s*\(", line) and language == "python":
                findings.append(self._finding(index, "low", "print_olvidado",
                    "Posible print() de depuración dejado en el código."))
            if re.search(r"(?i)\b(TODO|FIXME|HACK|XXX)\b", line):
                findings.append(self._finding(index, "info", "marcador_pendiente",
                    "Marcador de trabajo pendiente sin resolver."))

        if language == "python":
            findings.extend(self._python_findings(code, payload.max_function_lines))

        severities = ["high", "medium", "low", "info"]
        by_severity = {sev: sum(1 for f in findings if f["severity"] == sev) for sev in severities}
        quality_score = max(
            0.0,
            round(1.0 - (by_severity["high"] * 0.2 + by_severity["medium"] * 0.1
                         + by_severity["low"] * 0.03 + by_severity["info"] * 0.01), 2),
        )
        return {
            "language": language,
            "findings": findings[:100],
            "finding_count": len(findings),
            "by_severity": by_severity,
            "quality_score": quality_score,
            "note": "Heurístico: complementa, no sustituye, una revisión humana y un linter dedicado.",
        }

    def _python_findings(self, code: str, max_function_lines: int) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return [self._finding(exc.lineno or 0, "high", "error_sintaxis",
                f"El código no compila: {exc.msg}.")]

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(node, "end_lineno", node.lineno) or node.lineno
                length = end - node.lineno + 1
                if length > max_function_lines:
                    findings.append(self._finding(node.lineno, "medium", "funcion_larga",
                        f"La función '{node.name}' tiene ~{length} líneas (máx. {max_function_lines})."))
                total_args = len(node.args.args) + len(node.args.kwonlyargs)
                if total_args > 5:
                    findings.append(self._finding(node.lineno, "low", "demasiados_argumentos",
                        f"'{node.name}' recibe {total_args} argumentos: valora agruparlos."))
                if ast.get_docstring(node) is None and not node.name.startswith("_"):
                    findings.append(self._finding(node.lineno, "low", "sin_docstring",
                        f"La función pública '{node.name}' no tiene docstring."))
                if _cyclomatic_complexity(node) > 10:
                    findings.append(self._finding(node.lineno, "medium", "complejidad_alta",
                        f"'{node.name}' tiene complejidad ciclomática {_cyclomatic_complexity(node)} (>10)."))
                for default in node.args.defaults + node.args.kw_defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        findings.append(self._finding(node.lineno, "medium", "default_mutable",
                            f"'{node.name}' usa un argumento por defecto mutable (anti-patrón)."))
                        break
            elif isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append(self._finding(node.lineno, "medium", "except_desnudo",
                    "`except:` sin tipo captura todo, incluido KeyboardInterrupt."))
        return findings

    @staticmethod
    def _finding(line: int, severity: str, rule: str, message: str) -> dict[str, Any]:
        return {"line": line, "severity": severity, "rule": rule, "message": message}


# ---------------------------------------------------------------------------
# scan_code_security  (SAST heurístico con mapeo CWE)
# ---------------------------------------------------------------------------

_SECURITY_PATTERNS: list[dict[str, Any]] = [
    {"rule": "eval_exec", "cwe": "CWE-95", "severity": "high",
     "pattern": re.compile(r"\b(eval|exec)\s*\("),
     "message": "Uso de eval()/exec(): ejecución dinámica peligrosa de código."},
    {"rule": "command_injection", "cwe": "CWE-78", "severity": "high",
     "pattern": re.compile(r"(os\.system|subprocess\.\w+\([^)]*shell\s*=\s*True|`[^`]+`)"),
     "message": "Ejecución de comandos del sistema (posible inyección de comandos)."},
    {"rule": "unsafe_deserialization", "cwe": "CWE-502", "severity": "high",
     "pattern": re.compile(r"(pickle\.loads|yaml\.load\s*\((?![^)]*Loader)|marshal\.loads)"),
     "message": "Deserialización insegura de datos no confiables."},
    {"rule": "weak_hash", "cwe": "CWE-327", "severity": "medium",
     "pattern": re.compile(r"hashlib\.(md5|sha1)\s*\("),
     "message": "Algoritmo de hash débil (MD5/SHA1) para datos sensibles."},
    {"rule": "sql_injection", "cwe": "CWE-89", "severity": "high",
     "pattern": re.compile(r"(execute|query)\s*\(\s*[\"'].*?(\+|%|\{).*?[\"']|"
                           r"(select|insert|update|delete)\s.*?\"\s*\+\s*\w+", re.IGNORECASE),
     "message": "Posible SQL construido por concatenación (inyección SQL)."},
    {"rule": "tls_verification_disabled", "cwe": "CWE-295", "severity": "high",
     "pattern": re.compile(r"(verify\s*=\s*False|ssl\._create_unverified_context|InsecureRequestWarning)"),
     "message": "Verificación de certificados TLS desactivada."},
    {"rule": "hardcoded_secret", "cwe": "CWE-798", "severity": "high",
     "pattern": re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*[\"'][^\"']{6,}[\"']"),
     "message": "Posible credencial embebida en el código fuente."},
    {"rule": "insecure_random", "cwe": "CWE-330", "severity": "low",
     "pattern": re.compile(r"random\.(random|randint|choice|randrange)\s*\("),
     "message": "random no es criptográficamente seguro; usa 'secrets' para tokens."},
    {"rule": "debug_enabled", "cwe": "CWE-489", "severity": "medium",
     "pattern": re.compile(r"(?i)debug\s*=\s*True"),
     "message": "Modo debug activado: no debe llegar a producción."},
    {"rule": "wildcard_bind", "cwe": "CWE-1327", "severity": "low",
     "pattern": re.compile(r"0\.0\.0\.0"),
     "message": "Escucha en 0.0.0.0: revisa la exposición de red."},
]


class ScanCodeSecurityInput(BaseModel):
    code: str = Field(min_length=1, max_length=_MAX_CODE_CHARS)
    language: str | None = Field(default=None)


class ScanCodeSecurityTool(BaseTool):
    name = "scan_code_security"
    category = "programming"
    description = (
        "SAST heurístico defensivo: detecta patrones de riesgo (eval/exec, inyección "
        "de comandos y SQL, deserialización insegura, hash débil, TLS sin verificar, "
        "secretos embebidos) y los mapea a CWE. No sustituye un SAST profesional."
    )
    input_schema = ScanCodeSecurityInput
    timeout_seconds = 10

    def execute(self, payload: ScanCodeSecurityInput, ctx: ToolContext) -> dict[str, Any]:
        language = detect_language(payload.code, payload.language)
        findings: list[dict[str, Any]] = []
        for index, line in enumerate(payload.code.splitlines(), start=1):
            for spec in _SECURITY_PATTERNS:
                if spec["pattern"].search(line):
                    findings.append(
                        {
                            "line": index,
                            "severity": spec["severity"],
                            "rule": spec["rule"],
                            "cwe": spec["cwe"],
                            "message": spec["message"],
                            "snippet": line.strip()[:160],
                        }
                    )
        severities = ["high", "medium", "low"]
        by_severity = {sev: sum(1 for f in findings if f["severity"] == sev) for sev in severities}
        risk = "alto" if by_severity["high"] else "medio" if by_severity["medium"] else "bajo"
        return {
            "language": language,
            "findings": findings[:100],
            "finding_count": len(findings),
            "by_severity": by_severity,
            "cwes": sorted({f["cwe"] for f in findings}),
            "risk_level": risk,
            "note": (
                "Heurístico defensivo por patrones: pueden existir falsos positivos y "
                "negativos. Verifica cada hallazgo y complementa con herramientas dedicadas."
            ),
        }


# ---------------------------------------------------------------------------
# generate_test_skeleton
# ---------------------------------------------------------------------------


class GenerateTestSkeletonInput(BaseModel):
    code: str = Field(min_length=1, max_length=_MAX_CODE_CHARS, description="Código Python a cubrir con tests")
    framework: str = Field(default="pytest", pattern="^(pytest|unittest)$")


class GenerateTestSkeletonTool(BaseTool):
    name = "generate_test_skeleton"
    category = "programming"
    description = (
        "Genera esqueletos de tests (pytest o unittest) a partir de las funciones y "
        "métodos públicos de un módulo Python. Los cuerpos quedan pendientes de completar."
    )
    input_schema = GenerateTestSkeletonInput
    timeout_seconds = 10

    def execute(self, payload: GenerateTestSkeletonInput, ctx: ToolContext) -> dict[str, Any]:
        try:
            tree = ast.parse(payload.code)
        except SyntaxError as exc:
            raise ToolError(
                f"El código Python no compila (línea {exc.lineno}: {exc.msg}). "
                "Corrige la sintaxis antes de generar tests."
            ) from exc

        targets: list[str] = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                targets.append(node.name)
            elif isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and not sub.name.startswith("_"):
                        targets.append(f"{node.name}.{sub.name}")

        if not targets:
            return {"tests_generated": 0, "targets": [], "skeleton_code": "",
                    "note": "No se encontraron funciones o métodos públicos que cubrir."}

        if payload.framework == "pytest":
            skeleton = self._pytest_skeleton(targets)
        else:
            skeleton = self._unittest_skeleton(targets)
        return {
            "tests_generated": len(targets),
            "targets": targets,
            "framework": payload.framework,
            "skeleton_code": skeleton,
            "note": "Esqueletos orientativos: define Arrange/Act/Assert y casos límite reales.",
        }

    @staticmethod
    def _pytest_skeleton(targets: list[str]) -> str:
        blocks = ['"""Tests generados (esqueleto). Completa cada caso."""', "import pytest", ""]
        for target in targets:
            test_name = target.replace(".", "_").lower()
            blocks += [
                f"def test_{test_name}():",
                f'    """Caso base de {target}."""',
                "    # Arrange: prepara entradas y dependencias.",
                "    # Act: invoca el código bajo prueba.",
                "    # Assert: comprueba el resultado esperado.",
                "    raise NotImplementedError('Completar este test.')",
                "",
            ]
        return "\n".join(blocks)

    @staticmethod
    def _unittest_skeleton(targets: list[str]) -> str:
        blocks = ['"""Tests generados (esqueleto)."""', "import unittest", "", "", "class GeneratedTests(unittest.TestCase):"]
        for target in targets:
            test_name = target.replace(".", "_").lower()
            blocks += [
                f"    def test_{test_name}(self):",
                f'        """Caso base de {target}."""',
                "        self.fail('Completar este test.')",
                "",
            ]
        blocks += ["", 'if __name__ == "__main__":', "    unittest.main()"]
        return "\n".join(blocks)


# ---------------------------------------------------------------------------
# extract_code_todos
# ---------------------------------------------------------------------------

_TODO_PATTERN = re.compile(r"(?i)(?:#|//|/\*|\*|<!--)?\s*\b(TODO|FIXME|HACK|XXX|BUG)\b[:\-\s]*(.*)")


class ExtractCodeTodosInput(BaseModel):
    code: str = Field(min_length=1, max_length=_MAX_CODE_CHARS)


class ExtractCodeTodosTool(BaseTool):
    name = "extract_code_todos"
    category = "programming"
    description = (
        "Extrae marcadores de trabajo pendiente (TODO, FIXME, HACK, XXX, BUG) con su "
        "número de línea y el texto asociado, agrupados por tipo."
    )
    input_schema = ExtractCodeTodosInput
    timeout_seconds = 10

    def execute(self, payload: ExtractCodeTodosInput, ctx: ToolContext) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        by_tag: dict[str, int] = {}
        for index, line in enumerate(payload.code.splitlines(), start=1):
            match = _TODO_PATTERN.search(line)
            if match:
                tag = match.group(1).upper()
                text = match.group(2).strip().rstrip("*/->")[:200]
                items.append({"line": index, "tag": tag, "text": text})
                by_tag[tag] = by_tag.get(tag, 0) + 1
        return {
            "count": len(items),
            "items": items[:200],
            "by_tag": by_tag,
            "note": "FIXME y BUG suelen ser deuda prioritaria; TODO/HACK indican mejoras pendientes.",
        }
