FROM ubuntu:24.04 AS trainwatch-dev

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

ENV PYTHONPATH=/code
ENV FLASK_RUN_HOST=0.0.0.0

EXPOSE 5000

CMD ["python3", "run.py"]