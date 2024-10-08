FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip3 install -r requirements.txt

ADD app/*.py ./
ENTRYPOINT ["python3", "docker_mqtt_app.py"]
CMD ["-u"]