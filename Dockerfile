FROM python:3.11

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | POETRY_HOME=/opt/poetry python && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

# Copy using poetry.lock* in case it doesn't exist yet
COPY ./pyproject.toml ./poetry.lock* /app/

WORKDIR  /app/

RUN poetry install --no-root --only main

COPY ./src /app/

ENV GUNICORN_CMD_ARGS --proxy-protocol
ENV MODULE_NAME guid_slurp.main

# CMD ["gunicorn", "guid_slurp.main:app", "--proxy-protocol", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind"  , "0.0.0.0:80"]
