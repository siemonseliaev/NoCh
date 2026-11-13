import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import json

# Добавляем директорию src в системный путь через os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, os.path.join(parent_dir, "src"))

from TryKonf import (
    load_config,
    validate_config,
    fetch_test_graph_data,
    build_dependency_graph_dfs,
    generate_d2_code,
)


class TestDependencyAnalyzerStage5(unittest.TestCase):

    def setUp(self):
        """Создаем базовый корректный конфиг для тестов."""
        self.valid_config = {
            "package_name": "A",
            "repo_url": "test_graph.json",
            "repo_mode": "test",
            "package_version": "1.0.0",
            "output_image": "output.svg",
            "max_depth": 3,
        }

    def test_validate_config_success(self):
        """Проверка успешной валидации корректного словаря конфигурации."""
        try:
            validate_config(self.valid_config)
        except Exception as e:
            self.fail(f"validate_config вызвал исключение: {e}")

    def test_negative_max_depth(self):
        """Проверка ошибки ValueError при отрицательной глубине max_depth."""
        invalid_config = self.valid_config.copy()
        invalid_config["max_depth"] = -1
        with self.assertRaises(ValueError):
            validate_config(invalid_config)

    def test_missing_required_field(self):
        """Проверка ошибки KeyError при отсутствии обязательного поля."""
        invalid_config = self.valid_config.copy()
        del invalid_config["output_image"]
        with self.assertRaises(KeyError):
            validate_config(invalid_config)

    def test_build_dependency_graph_dfs(self):
        """Проверка нерекурсивного DFS построения графа с циклами (возвращает только словарь graph)."""
        mock_pkg_map = {
            "A": ["B", "C"],
            "B": ["D"],
            "C": [],
            "D": ["A"]  # Цикл A -> B -> D -> A
        }

        graph = build_dependency_graph_dfs(
            root_pkg="A",
            root_ver="1.0.0",
            mode="test",
            max_depth=3,
            pkg_map=mock_pkg_map
        )

        self.assertIn("A", graph)
        self.assertIn("B", graph["A"])
        self.assertIn("D", graph["B"])
        self.assertIsInstance(graph, dict)

    def test_generate_d2_code(self):
        """Проверка формирования текстового представления графа на языке D2 (Требование 1 Этапа 5)."""
        graph = {
            "serde": ["tokio", "syn"],
            "tokio": [],
            "syn": []
        }
        d2_code = generate_d2_code(graph)

        self.assertIn("direction: right", d2_code)
        self.assertIn('"serde" -> "tokio"', d2_code)
        self.assertIn('"serde" -> "syn"', d2_code)
        self.assertIn('"tokio"', d2_code)
        self.assertIsInstance(d2_code, str)


if __name__ == "__main__":
    unittest.main()