FROM python:3.9-slim
WORKDIR /app

COPY simple_sse.py /app/server.py

RUN pip install flask

EXPOSE 9626

CMD ["python", "/app/server.py"] 