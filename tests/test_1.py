import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
import json


sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "src")
)

from TryKonf import (
    load_config,
    validate_config,
    fetch_test_graph_data,
    build_dependency_graph_dfs,
    fetch_online_dependencies,
)


class TestDependencyAnalyzerStage3(unittest.TestCase):

    def setUp(self):
        """Создаем базовый корректный конфиг для тестов."""
        self.valid_config = {
            "package_name": "A",
            "repo_url": "test_graph.json",
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
            self.fail(f"validate_config вызвал исключение: {e}")

    def test_negative_max_depth(self):
        """Проверка ошибки ValueError при отрицательной глубине."""
        invalid_config = self.valid_config.copy()
        invalid_config["max_depth"] = -1
        with self.assertRaises(ValueError):
            validate_config(invalid_config)

    def test_invalid_repo_mode(self):
        """Проверка ошибки ValueError при некорректном режиме репозитория."""
        invalid_config = self.valid_config.copy()
        invalid_config["repo_mode"] = "invalid_mode"
        with self.assertRaises(ValueError):
            validate_config(invalid_config)

    def test_build_dependency_graph_dfs(self):
        """Проверка нерекурсивного DFS построения графа с циклами."""
        mock_pkg_map = {
            "A": ["B", "C"],
            "B": ["D"],
            "C": [],
            "D": ["A"]
        }

        graph, visited = build_dependency_graph_dfs(
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


if __name__ == "__main__":
    main_res = unittest.main(exit=False)