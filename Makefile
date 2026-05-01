.PHONY: help install install-dev test test-cov lint lint-fix format format-check clean

help:
	@echo "ptg-agent (Prometheus) 开发命令"
	@echo ""
	@echo "  make install      安装运行时依赖"
	@echo "  make install-dev  安装开发依赖 (含 ruff/pytest)"
	@echo "  make test         运行测试"
	@echo "  make test-cov     运行测试 + 覆盖率报告"
	@echo "  make lint         代码检查 (ruff)"
	@echo "  make lint-fix     自动修复 (ruff --fix)"
	@echo "  make format       格式化代码"
	@echo "  make format-check 检查格式 (CI 用)"
	@echo "  make check        全量检查 (lint + format + test)"
	@echo "  make clean        清理构建产物"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	python -m pytest prometheus/tests/ -v

test-cov:
	python -m pytest prometheus/tests/ -v --cov=prometheus --cov-report=term-missing --cov-report=html

lint:
	python -m ruff check prometheus/

lint-fix:
	python -m ruff check prometheus/ --fix

format:
	python -m ruff format prometheus/

format-check:
	python -m ruff format prometheus/ --check

check: lint format-check test
	@echo "✅ 全量检查通过"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage coverage.xml *.egg-info dist build
