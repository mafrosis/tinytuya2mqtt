.PHONY: build
build:
	docker compose build tinytuya2mqtt

.PHONY: run
run:
	docker compose up --no-build
