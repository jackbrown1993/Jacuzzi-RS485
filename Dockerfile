FROM python:alpine as base

FROM base as build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base
WORKDIR /app
COPY --from=build /install /usr/local
ADD *.py ./
ENTRYPOINT ["python3"]
CMD ["-u","app.py"]
VOLUME /images