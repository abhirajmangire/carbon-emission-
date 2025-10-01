FROM python:3.12-slim

WORKDIR /app

COPY energy_backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY energy_backend /app/energy_backend

ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

CMD ["python", "energy_backend/flask_app.py"]

