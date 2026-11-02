import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

# Добавляем директорию src в системный путь для импорта
sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "src")
)

from TryKonf import (
    load_config,
    validate_config,
    fetch_test_dependencies,
    fetch_cargo_dependencies,
    fetch_online_dependencies,
)


class TestCargoDependencyAnalyzer(unittest.TestCase):

    def setUp(self):
        """Создаем базовый корректный конфиг для тестов."""
        self.valid_config = {
            "package_name": "serde",
            "repo_url": "https://crates.io",
            "repo_mode": "test",
            "package_version": "1.0.0",
            "output_image": "output.png",
            "max_depth": 3,
        }

    def test_validate_config_success(self):
        """Проверка успешной валидации корректного словаря."""
        try:
            validate_config(self.valid_config)
        except Exception as e:
            self.fail(
                f"validate_config вызвал исключение на корректных данных: {e}"
            )

    def test_missing_field(self):
        """Проверка ошибки KeyError при отсутствии обязательного поля."""
        invalid_config = self.valid_config.copy()
        del invalid_config["package_name"]

        with self.assertRaises(KeyError):
            validate_config(invalid_config)

    def test_invalid_type(self):
        """Проверка ошибки TypeError при неверном типе данных поля."""
        invalid_config = self.valid_config.copy()
        invalid_config["max_depth"] = "three"

        with self.assertRaises(TypeError):
            validate_config(invalid_config)

    def test_bool_as_int(self):
        """Проверка того, что bool не принимается вместо int."""
        invalid_config = self.valid_config.copy()
        invalid_config["max_depth"] = True

        with self.assertRaises(TypeError):
            validate_config(invalid_config)

    def test_negative_max_depth(self):
        """Проверка ошибки ValueError при отрицательной глубине."""
        invalid_config = self.valid_config.copy()
        invalid_config["max_depth"] = -1

        with self.assertRaises(ValueError):
            validate_config(invalid_config)

    def test_invalid_repo_mode(self):
        """Проверка ошибки ValueError при некорректном режиме репозитория."""
        invalid_config = self.valid_config.copy()
        invalid_config["repo_mode"] = "super_mode"

        with self.assertRaises(ValueError):
            validate_config(invalid_config)

    def test_file_not_found(self):
        """Проверка FileNotFoundError при загрузке несуществующего файла."""
        with self.assertRaises(FileNotFoundError):
            load_config("non_existent_config_file_12345.toml")

    def test_fetch_test_dependencies(self):
        """Проверка возврата тестовых зависимостей."""
        deps = fetch_test_dependencies()
        self.assertIsInstance(deps, list)
        self.assertGreater(len(deps), 0)

    def test_fetch_cargo_dependencies_routing(self):
        """Проверка правильности вызова функций по режимам (режим test)."""
        deps = fetch_cargo_dependencies(
            "serde", "1.0.0", "mode"
        )
        # Так как mode не 'test' и не 'offline', он уйдет в online.
        # Проверим разделение через отдельный вызов test:
        test_deps = fetch_cargo_dependencies(
            "serde", "1.0.0", "test"
        )
        self.assertIn("serde = \"1.0\"", test_deps)

    @patch("TryKonf.urllib.request.urlopen")
    def test_fetch_online_dependencies_mock(self, mock_urlopen):
        """Проверка парсинга ответа онлайн API с использованием мока."""
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b'{"dependencies": [{"crate_id": "tokio", '
            b'"requirement": "^1.28", "kind": "normal"}]}'
        )
        mock_urlopen.return_value.__enter__.return_value = mock_response

        deps = fetch_online_dependencies("serde", "1.0.0")

        self.assertEqual(len(deps), 1)
        self.assertIn("tokio = \"^1.28\" (normal)", deps[0])


if __name__ == "__main__":
    unittest.main()
