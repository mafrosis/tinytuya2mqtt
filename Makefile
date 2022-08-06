.PHONY: build
build:
	docker compose build tinytuya2mqtt

.PHONY: run
run:
	docker compose up --no-build

.PHONY: lint
lint:
	docker compose run --rm --entrypoint=pylint test /src/tinytuya2mqtt
