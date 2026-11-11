import json
import os
import sys
import tomllib
import urllib.request
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = "config.toml"
ZERO_LIMIT = 0
USER_AGENT = "DependencyAnalyzerCLI"
CRATES_URL = "https://crates.io/api/v1/crates"


def load_config(file_path: str) -> dict:
    """Загружает и парсит TOML файл конфигурации."""
    config_path = os.path.join(BASE_DIR, file_path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Файл '{file_path}' не найден.")
    with open(config_path, "rb") as file_obj:
        return tomllib.load(file_obj)


def validate_config(config: dict) -> None:
    """Проверяет обязательные параметры конфигурации."""
    req_fields = {
        "package_name": str,
        "repo_url": str,
        "repo_mode": str,
        "package_version": str,
        "output_image": str,
        "max_depth": int,
    }
    for field, exp_type in req_fields.items():
        if field not in config:
            raise KeyError(f"Отсутствует параметр: '{field}'")
        if not isinstance(config[field], exp_type) or isinstance(config[field], bool):
            raise TypeError(f"Неверный тип параметра '{field}'.")
    if config["max_depth"] < ZERO_LIMIT:
        raise ValueError("Параметр 'max_depth' не может быть отрицательным.")


def fetch_test_graph_data(file_path: str) -> dict:
    """Загружает граф тестового репозитория из JSON-файла."""
    local_path = file_path if os.path.isabs(file_path) else os.path.join(BASE_DIR, file_path)
    with open(local_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_offline_dependencies(package_name: str) -> dict:
    """Возвращает зависимости в офлайн-режиме из TOML-файла."""
    local_path = package_name if os.path.isabs(package_name) else os.path.join(BASE_DIR, package_name)
    with open(local_path, "rb") as file_obj:
        data = tomllib.load(file_obj)
        return {dep: [ver] for dep, ver in data.get("dependencies", {}).items()}


def fetch_online_dependencies(package_name: str, version: str) -> list[str]:
    """Загружает прямые зависимости с crates.io."""
    api_url = f"{CRATES_URL}/{package_name}/{version}/dependencies"
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return [dep.get("crate_id") for dep in data.get("dependencies", []) if dep.get("kind") in ("normal", "dev")]


def build_dependency_graph_dfs(root_pkg: str, root_ver: str, mode: str, max_depth: int, pkg_map: dict) -> dict[
    str, list[str]]:
    """Строит граф зависимостей с помощью DFS."""
    graph, visited, stack = {}, set(), [(root_pkg, root_ver, 0, {root_pkg})]
    while stack:
        pkg, ver, depth, current_path = stack.pop()
        if pkg not in graph:
            graph[pkg] = []
        if depth >= max_depth:
            visited.add(pkg)
            continue

        raw_deps = pkg_map.get(pkg, []) if mode == "test" else (
            list(fetch_offline_dependencies(pkg).keys()) if mode == "offline" else fetch_online_dependencies(pkg, ver)
        )

        for dep in raw_deps:
            if dep not in graph[pkg]:
                graph[pkg].append(dep)
            if dep not in current_path and depth + 1 < max_depth and dep not in visited:
                stack.append((dep, "latest", depth + 1, current_path | {dep}))
        visited.add(pkg)
    return graph


def generate_d2_code(graph: dict[str, list[str]]) -> str:
    """Формирует текстовое представление графа на языке диаграмм D2."""
    d2_lines = ["direction: right\n"]
    for parent, children in graph.items():
        if not children:
            d2_lines.append(f'"{parent}"\n')
        for child in children:
            d2_lines.append(f'"{parent}" -> "{child}"\n')
    return "".join(d2_lines)


def run_stage_five(graph: dict[str, list[str]], output_image_path: str) -> None:
    """Выполняет визуализацию: генерирует D2 и сохраняет SVG."""
    print("\n[Этап 5] Генерация визуализации графа (D2 & SVG)...")
    d2_content = generate_d2_code(graph)

    d2_file_path = output_image_path.rsplit(".", 1)[0] + ".d2"
    with open(d2_file_path, "w", encoding="utf-8") as f:
        f.write(d2_content)

    svg_path = output_image_path if output_image_path.endswith(".svg") else output_image_path + ".svg"

    # Пытаемся скомпилировать через системную утилиту d2, если она установлена
    try:
        if subprocess.run(["d2", d2_file_path, svg_path], capture_output=True, text=True).returncode == 0:
            print(f"SVG успешно сгенерирован: {svg_path}")
            return
    except Exception:
        pass

    # Резервный вариант сохранения (в виде SVG-контейнера с кодом разметки)
    svg_fallback = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">
  <rect width="100%" height="100%" fill="#f4f4f4"/>
  <foreignObject x="20" y="20" width="560" height="360">
    <div xmlns="http://www.w3.org/1999/xhtml" style="font-family: monospace; font-size: 12px; white-space: pre-wrap;">{d2_content}</div>
  </foreignObject>
</svg>"""
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_fallback)
    print(f"SVG-файл сохранен: {svg_path}")


def main() -> None:
    """Точка входа CLI-приложения."""
    try:
        config = load_config(CONFIG_FILE)
        validate_config(config)

        pkg_name = config["package_name"]
        pkg_map = fetch_test_graph_data(pkg_name) if config["repo_mode"] == "test" else {}
        root_package = list(pkg_map.keys())[0] if pkg_map else pkg_name

        graph = build_dependency_graph_dfs(
            root_package, config["package_version"], config["repo_mode"], config["max_depth"], pkg_map
        )
        run_stage_five(graph, config["output_image"])

    except Exception as err:
        print(f"\n[ОШИБКА]: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()