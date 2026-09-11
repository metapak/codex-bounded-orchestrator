FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 app
COPY x_autopilot ./x_autopilot
COPY config/x-autopilot.cloud.toml ./config/x-autopilot.cloud.toml
USER app
EXPOSE 8080
CMD ["python", "-m", "x_autopilot", "--config", "config/x-autopilot.cloud.toml", "serve"]
