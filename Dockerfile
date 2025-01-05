FROM python:3.12-slim

RUN rm -rf /var/lib/apt/lists/*

WORKDIR /samowarium

COPY yoyo.ini .

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY ./migrations ./migrations
COPY ./src .

# port for prometheus metric server
EXPOSE 53000

ENTRYPOINT [ "python3", "samowarium.py" ]