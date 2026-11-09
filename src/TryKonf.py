import os
import sys
import tomllib

CONFIG_FILE = "config.toml"
ZERO_LIMIT = 0


def load_config(file_path: str) -> dict:
    """Загружает и парсит TOML файл конфигурации."""
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(curr_dir, file_path)

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Файл конфигурации '{file_path}' не найден."
        )

    try:
        with open(config_path, "rb") as file_obj:
            return tomllib.load(file_obj)
    except tomllib.TOMLDecodeError as err:
        raise ValueError(f"Ошибка синтаксиса TOML: {err}")

def validate_config(config: dict) -> None:
    """Проверяет наличие и корректность типов всех обязательных параметров."""
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
                f"Отсутствует обязательный параметр: '{field}'"
            )

        val = config[field]
        is_bool = isinstance(val, bool)
        if not isinstance(val, exp_type) or (
            exp_type is int and is_bool
        ):
            raise TypeError(
                f"Неверный тип для параметра '{field}'. "
                f"Ожидался {exp_type.__name__}, "
                f"получен {type(val).__name__}"
            )

    if config["max_depth"] < ZERO_LIMIT:
        raise ValueError(
            "Параметр 'max_depth' не может быть меньше 0."
        )

    valid_modes = ["online", "offline", "test"]
    if config["repo_mode"] not in valid_modes:
        raise ValueError(
            f"Некорректный режим 'repo_mode': '{config['repo_mode']}'. "
            f"Допустимые значения: {valid_modes}"
        )


def main() -> None:
    """Точка входа приложения (Этап 1)."""
    print("=== Этап 1: Минимальный прототип с конфигурацией ===")
    try:
        config = load_config(CONFIG_FILE)
        validate_config(config)

        print("\nПараметры конфигурации:")
        for key, value in config.items():
            print(f"  - {key} = {value}")

    except (
        FileNotFoundError,
        ValueError,
        KeyError,
        TypeError,
    ) as err:
        print(
            f"\n[ОШИБКА]: {err}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()