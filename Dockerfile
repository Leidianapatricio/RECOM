FROM python:3.12

WORKDIR /code

COPY requirements.txt .

RUN apt-get update && apt-get install -y gettext

RUN pip install -r requirements.txt

COPY . .