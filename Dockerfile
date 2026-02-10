FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir gunicorn

COPY . .

# Create entrypoint script that generates migrations
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Making migrations..."\n\
python manage.py makemigrations --noinput\n\
echo "Running migrations..."\n\
python manage.py migrate --noinput\n\
echo "Collecting static files..."\n\
python manage.py collectstatic --noinput\n\
echo "Starting gunicorn..."\n\
exec gunicorn --bind 0.0.0.0:${PORT:-8000} \
    --workers=1 \
    --threads=2 \
    --timeout=300 \
    --access-logfile - \
    --error-logfile - \
    vizitAfricaBackend.wsgi:application' > /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
