import json
import os
import sys
import tomllib
import urllib.request
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = "config.toml"
ZERO_LIMIT = 0
USER_AGENT = "DependencyAnalyzerCLI (contact@example.com)"
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
        is_invalid_type = (
                not isinstance(config[field], exp_type)
                or isinstance(config[field], bool)
        )
        if is_invalid_type:
            raise TypeError(f"Неверный тип параметра '{field}'.")
    if config["max_depth"] < ZERO_LIMIT:
        raise ValueError("Параметр 'max_depth' не может быть отрицательным.")


def fetch_test_graph_data(file_path: str) -> dict:
    """Загружает граф тестового репозитория из JSON-файла."""
    is_abs = os.path.isabs(file_path)
    local_path = file_path if is_abs else os.path.join(BASE_DIR, file_path)
    with open(local_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_offline_dependencies(package_name: str) -> dict:
    """Возвращает зависимости в офлайн-режиме из TOML."""
    is_abs = os.path.isabs(package_name)
    local_path = package_name if is_abs else os.path.join(BASE_DIR, package_name)
    with open(local_path, "rb") as file_obj:
        data = tomllib.load(file_obj)
        deps = data.get("dependencies", {})
        return {dep: [ver] for dep, ver in deps.items()}


def _select_target_version(versions: list, version: str) -> dict | None:
    """Выбирает нужную версию пакета из списка доступных."""
    if version == "latest" or not version:
        return versions[0] if versions else None

    for v in versions:
        if v.get("num") == version:
            return v
    return versions[0] if versions else None


def _get_crate_dependencies(
        package_name: str, ver_num: str
) -> list[str]:
    """Загружает список зависимостей для конкретной версии."""
    deps_url = f"{CRATES_URL}/{package_name}/{ver_num}/dependencies"
    req_deps = urllib.request.Request(
        deps_url, headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req_deps) as resp_deps:
        deps_data = json.loads(resp_deps.read().decode("utf-8"))
        raw_deps = deps_data.get("dependencies", [])
        return [
            dep.get("crate_id")
            for dep in raw_deps
            if dep.get("kind") in ("normal", "dev")
        ]


def fetch_online_dependencies(package_name: str, version: str) -> list[str]:
    """Загружает прямые зависимости с crates.io."""
    api_url = f"{CRATES_URL}/{package_name}"
    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            versions = data.get("versions", [])
            target = _select_target_version(versions, version)
            if not target:
                return []

            ver_num = target.get("num")
            return _get_crate_dependencies(package_name, ver_num)
    except urllib.error.HTTPError as e:
        if e.code in (400, 404) and version != "latest":
            return fetch_online_dependencies(package_name, "latest")
        raise RuntimeError(
            f"Ошибка запроса к crates.io для '{package_name}': HTTP {e.code}"
        )


def _get_raw_dependencies(pkg: str, ver: str, mode: str, pkg_map: dict) -> list:
    """Возвращает сырые зависимости в зависимости от режима."""
    if mode == "test":
        return pkg_map.get(pkg, [])
    elif mode == "offline":
        return list(fetch_offline_dependencies(pkg).keys())
    else:
        return fetch_online_dependencies(pkg, ver)


def build_dependency_graph_dfs(
        root_pkg: str, root_ver: str, mode: str, max_depth: int, pkg_map: dict
) -> dict[str, list[str]]:
    """Строит граф зависимостей с помощью DFS."""
    graph, visited = {}, set()
    stack = [(root_pkg, root_ver, 0, {root_pkg})]

    while stack:
        pkg, ver, depth, current_path = stack.pop()
        if pkg not in graph:
            graph[pkg] = []
        if depth >= max_depth:
            visited.add(pkg)
            continue

        raw_deps = _get_raw_dependencies(pkg, ver, mode, pkg_map)

        for dep in raw_deps:
            if dep not in graph[pkg]:
                graph[pkg].append(dep)
            not_visited = dep not in current_path
            under_depth = depth + 1 < max_depth
            if not_visited and under_depth and dep not in visited:
                stack.append((dep, "latest", depth + 1, current_path | {dep}))
        visited.add(pkg)
    return graph


def generate_d2_code(graph: dict[str, list[str]]) -> str:
    """Формирует текстовое представление графа на D2."""
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

    svg_path = (
        output_image_path
        if output_image_path.endswith(".svg")
        else output_image_path + ".svg"
    )

    try:
        res = subprocess.run(
            ["d2", d2_file_path, svg_path],
            capture_output=True,
            text=True
        )
        if res.returncode == 0:
            print(f"SVG успешно сгенерирован: {svg_path}")
            return
    except Exception:
        pass

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

        repo_mode = config["repo_mode"]
        pkg_name = config["package_name"]
        pkg_version = config["package_version"]

        pkg_map = fetch_test_graph_data(pkg_name) if repo_mode == "test" else {}
        root_package = list(pkg_map.keys())[0] if (repo_mode == "test" and pkg_map) else pkg_name

        graph = build_dependency_graph_dfs(
            root_package, pkg_version, repo_mode, config["max_depth"], pkg_map
        )
        run_stage_five(graph, config["output_image"])

    except Exception as err:
        print(f"\n[ОШИБКА]: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()