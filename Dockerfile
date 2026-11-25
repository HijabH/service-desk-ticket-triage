FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY triage ./triage
EXPOSE 8000
# runs as a non-root user
RUN useradd --create-home appuser
USER appuser
CMD ["uvicorn", "triage.api:app", "--host", "0.0.0.0", "--port", "8000"]
