import unittest
from unittest.mock import patch, mock_open
import os
import sys

# Добавляем директорию src в системный путь для импорта с использованием модуля os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
src_path = os.path.join(parent_dir, "src")
sys.path.insert(0, src_path)

from TryKonf import (
    load_config,
    validate_config,
)


class TestStage1Config(unittest.TestCase):

    def setUp(self):
        """Создаем базовый корректный словарь конфигурации для тестов."""
        self.valid_config = {
            "package_name": "serde",
            "repo_url": "https://github.com/example/repo",
            "repo_mode": "test",
            "package_version": "1.0.200",
            "output_image": "output.png",
            "max_depth": 3,
        }

    def test_validate_config_success(self):
        """Проверка успешной валидации корректного словаря конфигурации."""
        try:
            validate_config(self.valid_config)
        except Exception as e:
            self.fail(f"validate_config вызвал непредвиденное исключение: {e}")

    def test_missing_required_field(self):
        """Проверка выброса KeyError, если отсутствует обязательный параметр."""
        for field in self.valid_config.keys():
            invalid_config = self.valid_config.copy()
            del invalid_config[field]
            with self.assertRaises(KeyError):
                validate_config(invalid_config)

    def test_invalid_type_field(self):
        """Проверка выброса TypeError при неверном типе данных параметра."""
        invalid_config = self.valid_config.copy()
        invalid_config["package_name"] = 123
        with self.assertRaises(TypeError):
            validate_config(invalid_config)

        invalid_config_bool = self.valid_config.copy()
        invalid_config_bool["max_depth"] = True
        with self.assertRaises(TypeError):
            validate_config(invalid_config_bool)

    def test_negative_max_depth(self):
        """Проверка выброса ValueError при отрицательном значении max_depth."""
        invalid_config = self.valid_config.copy()
        invalid_config["max_depth"] = -1
        with self.assertRaises(ValueError):
            validate_config(invalid_config)

    def test_invalid_repo_mode(self):
        """Проверка выброса ValueError при недопустимом значении repo_mode."""
        invalid_config = self.valid_config.copy()
        invalid_config["repo_mode"] = "unsupported_mode"
        with self.assertRaises(ValueError):
            validate_config(invalid_config)

    @patch("builtins.open", new_callable=mock_open, read_data=b"""
        package_name = "serde"
        repo_url = "https://github.com/example/repo"
        repo_mode = "online"
        package_version = "1.0.200"
        output_image = "output.png"
        max_depth = 5
    """)
    @patch("os.path.exists", return_value=True)
    def test_load_config_success(self, mock_exists, mock_file):
        """Проверка успешной загрузки и парсинга TOML файла."""
        config = load_config("config.toml")
        self.assertEqual(config["package_name"], "serde")
        self.assertEqual(config["repo_mode"], "online")
        self.assertEqual(config["max_depth"], 5)

    @patch("os.path.exists", return_value=False)
    def test_load_config_file_not_found(self, mock_exists):
        """Проверка выброса FileNotFoundError, если файл конфигурации не существует."""
        with self.assertRaises(FileNotFoundError):
            load_config("nonexistent.toml")


if __name__ == "__main__":
    unittest.main()