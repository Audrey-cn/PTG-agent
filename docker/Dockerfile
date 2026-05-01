FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir ptg

EXPOSE 8765

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
