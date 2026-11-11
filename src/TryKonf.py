import json
import os
import sys
import tomllib
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = "config.toml"
ZERO_LIMIT = 0
USER_AGENT = "DependencyAnalyzerCLI"
CRATES_URL = "https://crates.io/api/v1/crates"


def load_config(file_path: str) -> dict:
    """Загружает и парсит TOML файл конфигурации."""
    config_path = os.path.join(BASE_DIR, file_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Файл '{file_path}' не найден по пути: {config_path}"
        )

    try:
        with open(config_path, "rb") as file_obj:
            return tomllib.load(file_obj)
    except tomllib.TOMLDecodeError as err:
        raise ValueError(f"Ошибка синтаксиса TOML: {err}")


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

        val = config[field]
        is_bool = isinstance(val, bool)
        if not isinstance(val, exp_type) or (
            exp_type is int and is_bool
        ):
            raise TypeError(
                f"Неверный тип '{field}'. "
                f"Ожидался {exp_type.__name__}, "
                f"получен {type(val).__name__}"
            )

    if config["max_depth"] < ZERO_LIMIT:
        raise ValueError("Параметр 'max_depth' < 0.")

    valid_modes = ["online", "offline", "test"]
    if config["repo_mode"] not in valid_modes:
        raise ValueError(
            f"Некорректный режим 'repo_mode': "
            f"'{config['repo_mode']}'"
        )


def fetch_test_graph_data(file_path: str) -> dict:
    """Загружает граф тестового репозитория из JSON-файла."""
    if os.path.isabs(file_path):
        local_path = file_path
    else:
        local_path = os.path.join(BASE_DIR, file_path)

    if not os.path.exists(local_path):
        raise FileNotFoundError(
            f"Тестовый файл графа не найден: {local_path}"
        )

    try:
        with open(local_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as err:
        raise ValueError(f"Ошибка чтения тестового файла: {err}")


def fetch_offline_dependencies(package_name: str) -> dict:
    """Возвращает зависимости в офлайн-режиме из TOML-файла."""
    if os.path.isabs(package_name):
        local_path = package_name
    else:
        local_path = os.path.join(BASE_DIR, package_name)

    if os.path.exists(local_path) and os.path.isfile(local_path):
        with open(local_path, "rb") as file_obj:
            data = tomllib.load(file_obj)
            deps = data.get("dependencies", {})
            return {dep: [ver] for dep, ver in deps.items()}
    raise FileNotFoundError(f"Файл не найден: {local_path}")


def fetch_online_dependencies(
    package_name: str,
    version: str
) -> list[str]:
    """Загружает прямые зависимости с crates.io."""
    dependencies = []
    api_url = f"{CRATES_URL}/{package_name}/{version}/dependencies"
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(api_url, headers=headers)

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for dep in data.get("dependencies", []):
                dep_name = dep.get("crate_id")
                kind = dep.get("kind")
                if kind in ("normal", "dev"):
                    dependencies.append(dep_name)
    except Exception as err:
        raise RuntimeError(
            f"Ошибка API crates.io для {package_name}: {err}"
        )

    return dependencies


def process_dependencies(
    pkg: str,
    ver: str,
    mode: str,
    pkg_map: dict
) -> list[str]:
    """Получает список зависимостей узла в зависимости от режима."""
    if mode == "test":
        return pkg_map.get(pkg, [])
    elif mode == "offline":
        return list(fetch_offline_dependencies(pkg).keys())
    else:
        return fetch_online_dependencies(pkg, ver)


def build_dependency_graph_dfs(
    root_pkg: str,
    root_ver: str,
    mode: str,
    max_depth: int,
    pkg_map: dict
) -> tuple[dict[str, list[str]], set[str]]:
    """Строит граф зависимостей с помощью нерекурсивного DFS."""
    graph = {}
    visited = set()
    stack = [(root_pkg, root_ver, 0, {root_pkg})]

    print(
        f"\n[Этап 3] Построение графа (DFS, "
        f"max_depth={max_depth}, mode={mode})..."
    )

    while stack:
        pkg, ver, depth, current_path = stack.pop()

        if pkg not in graph:
            graph[pkg] = []

        if depth >= max_depth:
            visited.add(pkg)
            continue

        try:
            raw_deps = process_dependencies(pkg, ver, mode, pkg_map)

            for dep in raw_deps:
                if dep not in graph[pkg]:
                    graph[pkg].append(dep)

                if dep in current_path:
                    print(f"Циклическая зависимость: {pkg} -> {dep}")
                    continue

                if depth + 1 < max_depth:
                    new_path = current_path | {dep}
                    stack.append((dep, "latest", depth + 1, new_path))

            visited.add(pkg)
        except Exception as err:
            print(f"Ошибка обработки узла {pkg}: {err}")

    return graph, visited


def main() -> None:
    """Точка входа CLI-приложения."""
    try:
        config = load_config(CONFIG_FILE)
        validate_config(config)

        pkg_name = config["package_name"]
        pkg_version = config["package_version"]
        repo_mode = config["repo_mode"]
        max_depth = config["max_depth"]

        pkg_map = {}
        if repo_mode == "test":
            pkg_map = fetch_test_graph_data(pkg_name)
            root_package = list(pkg_map.keys())[0] if pkg_map else pkg_name
        else:
            root_package = pkg_name

        graph, _ = build_dependency_graph_dfs(
            root_package, pkg_version, repo_mode, max_depth, pkg_map
        )

        print(f"\nРезультат построения графа (Узлов: {len(graph)}):")
        for parent, children in graph.items():
            print(f"  {parent} -> {children}")

    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError
    ) as err:
        print(f"\n[ОШИБКА]: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()