import json
import os
import sys
import tomllib
import urllib.request

CONFIG_FILE = "config.toml"
ZERO_LIMIT = 0


def load_config(file_path: str) -> dict:
    """Загружает и парсит TOML файл конфигурации."""
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(curr_dir, file_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Файл '{file_path}' не найден."
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
            raise KeyError(
                f"Отсутствует параметр: '{field}'"
            )

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
        raise ValueError(
            "Параметр 'max_depth' < 0."
        )

    valid_modes = ["online", "offline", "test"]
    if config["repo_mode"] not in valid_modes:
        raise ValueError(
            f"Некорректный режим 'repo_mode': "
            f"'{config['repo_mode']}'"
        )


def fetch_test_dependencies() -> list[str]:
    """Возвращает тестовые зависимости для режима test."""
    print("[Режим TEST] Тестовые данные.")
    return ["serde = \"1.0\"", "tokio = \"1.28\""]


def fetch_offline_dependencies(
    package_name: str
) -> list[str]:
    """Возвращает зависимости в офлайн-режиме."""
    print("[Режим OFFLINE] Чтение файла...")
    dependencies = []
    local_path = package_name
    if os.path.exists(local_path) and os.path.isfile(local_path):
        with open(local_path, "rb") as file_obj:
            data = tomllib.load(file_obj)
            deps = data.get("dependencies", {})
            for dep, ver in deps.items():
                dependencies.append(
                    f"{dep} = \"{ver}\""
                )
        return dependencies
    raise FileNotFoundError(
        f"Файл не найден: {local_path}"
    )


def fetch_online_dependencies(
    package_name: str,
    version: str
) -> list[str]:
    """Загружает прямые зависимости с crates.io."""
    dependencies = []
    base_url = "https://crates.io/api/v1/crates"
    api_url = (
        f"{base_url}/{package_name}/"
        f"{version}/dependencies"
    )
    headers = {
        "User-Agent": "DependencyAnalyzerCLI"
    }
    req = urllib.request.Request(
        api_url,
        headers=headers
    )

    print(
        f"[Режим ONLINE] Запрос к API "
        f"для {package_name} ({version})..."
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(
                resp.read().decode("utf-8")
            )
            for dep in data.get("dependencies", []):
                dep_name = dep.get("crate_id")
                dep_req = dep.get("requirement")
                kind = dep.get("kind")
                if kind in ("normal", "dev"):
                    dependencies.append(
                        f"{dep_name} = "
                        f"\"{dep_req}\" ({kind})"
                    )
    except Exception as err:
        raise RuntimeError(
            f"Ошибка API crates.io: {err}"
        )

    return dependencies


def fetch_cargo_dependencies(
    package_name: str,
    version: str,
    mode: str
) -> list[str]:
    """Получает прямые зависимости Cargo-пакета."""
    if mode == "test":
        return fetch_test_dependencies()
    if mode == "offline":
        return fetch_offline_dependencies(
            package_name
        )
    return fetch_online_dependencies(
        package_name,
        version
    )


def main() -> None:
    """Точка входа CLI-приложения."""
    print("=== Инициализация CLI (Этап 2) ===")
    try:
        config = load_config(CONFIG_FILE)
        validate_config(config)

        print("\n[Успешно] Конфигурация:")
        for key, value in config.items():
            print(f"  - {key} = {value}")

        print("\n--- Сбор зависимостей (Cargo) ---")
        pkg_name = config["package_name"]
        pkg_version = config["package_version"]
        repo_mode = config["repo_mode"]

        dependencies = fetch_cargo_dependencies(
            pkg_name,
            pkg_version,
            repo_mode
        )

        print(
            f"\nПрямые зависимости пакета "
            f"'{pkg_name}' ({pkg_version}):"
        )
        if dependencies:
            for dep in dependencies:
                print(f"  + {dep}")
        else:
            print("  (Зависимости не найдены)")

    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
    ) as err:
        print(
            f"\n[ОШИБКА]: {err}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()