FROM python:3.12

RUN apt-get update && \
    apt-get install -y gosu && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN chmod 755 /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN adduser --disabled-password articles_user

COPY ./entrypoint.sh .
RUN sed -i 's/\r$//g' entrypoint.sh
RUN chmod +x entrypoint.sh

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY . .

ENTRYPOINT ["/app/entrypoint.sh"]
