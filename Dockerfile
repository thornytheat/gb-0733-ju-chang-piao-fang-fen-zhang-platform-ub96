FROM python:3.12-slim
WORKDIR /project
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 18422
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "18422"]
