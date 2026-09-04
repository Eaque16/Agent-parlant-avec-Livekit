FROM node:22-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-agent.txt ./
RUN pip install --no-cache-dir -r requirements-agent.txt
COPY app ./app
COPY agent ./agent
COPY --from=frontend /src/app/static ./app/static
RUN mkdir -p /app/data && useradd --create-home app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
