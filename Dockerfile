FROM python:3.9-slim AS builder

# Dependencies for compiling python packages
RUN apt-get update && apt-get install -y build-essential

WORKDIR /src

# Build a wheel of tinytuya2mqtt
COPY requirements.txt /src/
RUN python -m pip wheel -r requirements.txt --wheel-dir /dist


FROM python:3.9-slim

WORKDIR /src

# Copy the built wheel, and essential package files
COPY --from=builder /dist /dist
COPY setup.py requirements.txt README.md /src/
COPY tinytuya2mqtt /src/tinytuya2mqtt

# Install dependencies and wheel
RUN python -m pip wheel --no-deps --wheel-dir /dist .
RUN python -m pip install --no-index --find-links=/dist tinytuya2mqtt

CMD ["tinytuya2mqtt"]
