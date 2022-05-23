FROM python:3.9-slim AS builder

WORKDIR /src

COPY requirements.txt /src/
RUN python -m pip install -r requirements.txt

COPY setup.py README.md /src/
COPY tinytuya2mqtt /src/tinytuya2mqtt

RUN python -m pip wheel --no-deps --wheel-dir /src/dist .
RUN python -m pip install --no-index --find-links=/src/dist tinytuya2mqtt

CMD ["tinytuya2mqtt"]
