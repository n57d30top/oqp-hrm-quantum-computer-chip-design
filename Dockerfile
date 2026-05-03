FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md licence.md LICENSE-CODE.md requirements-lock.txt Makefile ./
COPY oqp ./oqp
COPY tests ./tests
COPY docs ./docs
COPY hardware ./hardware
COPY architecture ./architecture
COPY reports ./reports
COPY ARTIFACTS.md ARTIFACTS.sha256 COMMERCIAL-LICENSING.md VALIDATION_ROADMAP.md ./

RUN python -m pip install --upgrade pip \
    && make install

CMD ["make", "ci"]
