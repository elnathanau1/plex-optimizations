# pull official base image
FROM python:3.9.5-slim-buster

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DATABASE postgres
ENV DATABASE_URL postgresql://postgres:postgres@192.168.0.197:5432/postgres
ENV FLASK_APP project/__init__.py
ENV FLASK_ENV development
ENV SQL_HOST 192.168.0.197
ENV SQL_PORT 5432

# install system dependencies
RUN apt-get update && apt-get install -y netcat

# install dependencies
RUN pip install --upgrade pip
COPY requirements.txt /usr/src/app/requirements.txt
RUN pip install -r requirements.txt

# copy project
COPY . /usr/src/app/

EXPOSE 5000

# run entrypoint.sh
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]

CMD python manage.py run -h 0.0.0.0