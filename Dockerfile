FROM python:3.13-alpine

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache uv

RUN uv sync --locked

COPY . .

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]