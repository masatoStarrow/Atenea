FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Recopilar archivos estaticos para produccion
RUN DJANGO_SETTINGS_MODULE=config.settings.local \
    DJANGO_SECRET_KEY=build-placeholder \
    python manage.py collectstatic --noinput 2>/dev/null || true

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["bash", "./entrypoint.sh"]
