"""Offline AST inventory: no application imports, database or provider connections."""

import ast
import json
from pathlib import Path


def inventory() -> dict[str, object]:
    root = Path("apps/api/vayujit_api")
    endpoints = []
    models = []
    modules = []
    for file in sorted(root.rglob("*.py")):
        tree = ast.parse(file.read_text(encoding="utf-8-sig"))
        prefixes = {}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "APIRouter"
            ):
                prefix = next(
                    (
                        k.value.value
                        for k in node.value.keywords
                        if k.arg == "prefix" and isinstance(k.value, ast.Constant)
                    ),
                    "",
                )
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        prefixes[target.id] = prefix
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if (
                        isinstance(item, ast.Assign)
                        and any(
                            isinstance(t, ast.Name) and t.id == "__tablename__"
                            for t in item.targets
                        )
                        and isinstance(item.value, ast.Constant)
                    ):
                        models.append(
                            {
                                "model": node.name,
                                "table": item.value.value,
                                "source": file.as_posix(),
                                "line": node.lineno,
                            }
                        )
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(
                    decorator.func, ast.Attribute
                ):
                    continue
                call = decorator.func
                if call.attr not in {
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                    "head",
                    "options",
                } or not isinstance(call.value, ast.Name):
                    continue
                if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
                    continue
                endpoints.append(
                    {
                        "method": call.attr.upper(),
                        "path": str(prefixes.get(call.value.id, "")) + str(decorator.args[0].value),
                        "source": file.as_posix(),
                        "handler": node.name,
                        "line": node.lineno,
                        "registration": "DECLARED_STATIC_NOT_RUNTIME_REACHABILITY",
                    }
                )
        if file.name.endswith("service.py") or file.name.endswith("worker.py"):
            modules.append(file.as_posix())
    tests = []
    for file in sorted(Path("apps/api/tests").rglob("test_*.py")):
        tree = ast.parse(file.read_text(encoding="utf-8-sig"))
        tests.append(
            {
                "source": file.as_posix(),
                "functions": sum(
                    isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and n.name.startswith("test_")
                    for n in ast.walk(tree)
                ),
                "executed": False,
            }
        )
    return {
        "api_declarations": endpoints,
        "models": models,
        "services_workers": modules,
        "backend_tests": tests,
    }


if __name__ == "__main__":
    print(json.dumps(inventory()))
