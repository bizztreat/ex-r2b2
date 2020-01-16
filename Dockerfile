FROM quay.io/keboola/docker-custom-python:latest

COPY ./requirements.txt /code/requirements.txt

RUN python -u -m pip install -r /code/requirements.txt

COPY ./src/ /code/
WORKDIR /data/

CMD ["python", "-u", "/code/main.py", "--config", "/data/config.json", "--outpath", "/data/out/tables", "--loglevel", "INFO"]

