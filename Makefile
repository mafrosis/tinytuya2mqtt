.PHONY: build
build:
	docker compose build tinytuya2mqtt

.PHONY: run
run:
	docker compose up --no-build

.PHONY: lint
lint:
	docker compose run --rm --entrypoint=pylint test /src/tinytuya2mqtt

.PHONY: typecheck
typecheck:
	docker compose run --rm test --mypy /src/tinytuya2mqtt

.PHONY: gen-stubs
gen-stubs:
	mkdir -p stubs
	mkdir -p tmp
	git clone https://github.com/eclipse/paho.mqtt.python.git tmp/paho.mqtt.python
	cd tmp/paho.mqtt.python/src/paho && \
		stubgen -v -p paho.mqtt -o ../../../../stubs
	touch stubs/paho/__init__.pyi
	git clone https://github.com/jasonacox/tinytuya.git tmp/tinytuya
	cd tmp/tinytuya/tinytuya && \
		stubgen -v -p tinytuya -o ../../../stubs
	rm -rf tmp
