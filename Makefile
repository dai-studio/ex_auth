.PHONY: setup start test format

setup:
	conda env create -f environment.yml || conda env update -f environment.yml --prune

start:
	uvicorn main:app --host $${HOST:-0.0.0.0} --port $${PORT:-8000} --reload

test:
	pytest tests/ -v

format:
	black main.py tests/
