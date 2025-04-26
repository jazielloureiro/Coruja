FROM python:3.13

WORKDIR /app

RUN pip install pipenv

COPY Pipfile Pipfile.lock ./

RUN pipenv install

COPY ./common ./common
COPY ./entities ./entities
COPY ./storage ./storage
COPY ./bot.py .

CMD ["pipenv", "run", "python", "bot.py"]