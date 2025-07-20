FROM python:3.12

WORKDIR /app
RUN chmod 755 /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN adduser --disabled-password articles_user

RUN mkdir logs
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
