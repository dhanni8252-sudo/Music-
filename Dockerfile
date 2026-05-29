FROM python:3.10-slim

# FFmpeg install karna
RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /app
COPY . /app

# Requirements install karna
RUN pip install -r requirements.txt

# Render ke port error ko bypass karne ke liye dummy server aur bot ek sath run karna
ENV PORT=10000
CMD python -m http.server $PORT & python bot.py

