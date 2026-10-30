.PHONY: help test lint typecheck dev run dashboard api clean

help:
	@echo "Comandos disponibles:"
	@echo "  make run        Iniciar el motor del bot (src/main.py)"
	@echo "  make api        Iniciar la API REST y WebSockets con FastAPI (puerto 8000)"
	@echo "  make dashboard  Abrir el dashboard interactivo de Streamlit"
	@echo "  make test       Ejecutar pruebas automatizadas con pytest"
	@echo "  make lint       Revisar estilo y código con ruff"
	@echo "  make typecheck  Verificar tipos estáticos con mypy"
	@echo "  make dev        Levantar servicios locales con Docker Compose"
	@echo "  make clean      Limpiar archivos temporales y cachés"

run:
	python -m src.main

dashboard:
	streamlit run src/reporting/dashboard/app.py

api:
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest -v tests/

lint:
	ruff check .

typecheck:
	mypy src/

dev:
	docker compose -f docker/docker-compose.yml up -d

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__ src/**/__pycache__ tests/**/__pycache__
