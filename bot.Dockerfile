FROM python:3.12

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY ./common ./common
COPY ./entities ./entities
COPY ./storage ./storage
COPY ./bot.py .

CMD ["python", "bot.py"]