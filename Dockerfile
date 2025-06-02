FROM python:3.12.10-slim

ARG TARGETARCH
ENV TARGETARCH ${TARGETARCH}

WORKDIR /src

COPY ./src .
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 3030

CMD ["python", "cmd/main.py"]