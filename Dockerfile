FROM python:3.9-slim AS builder

RUN apt-get update && apt-get install -y build-essential

WORKDIR /src

COPY requirements.txt /src/
RUN python -m pip wheel -r requirements.txt --wheel-dir /dist


FROM python:3.9-slim

WORKDIR /src

COPY --from=builder /dist /dist
COPY setup.py requirements.txt README.md /src/
COPY tinytuya2mqtt /src/tinytuya2mqtt

RUN python -m pip wheel --no-deps --wheel-dir /dist .
RUN python -m pip install --no-index --find-links=/dist tinytuya2mqtt

CMD ["tinytuya2mqtt"]
