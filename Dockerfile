FROM python:3.10

RUN apt update && apt install -y netcat-traditional

WORKDIR /app
RUN chmod 755 /app

RUN adduser --disabled-password articles_user

RUN mkdir logs && touch logs/info.log logs/uncatched_errors.log
RUN mkdir staticfiles

COPY ./entrypoint.sh .
RUN sed -i 's/\r$//g' entrypoint.sh
RUN chmod +x entrypoint.sh

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY . .

RUN chown -R articles_user: /app
USER articles_user

ENTRYPOINT ["/app/entrypoint.sh"]