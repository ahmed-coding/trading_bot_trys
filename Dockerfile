FROM python:3.10-alpine

# تثبيت المتطلبات الأساسية للنظام باستخدام apk
RUN apk update && \
    apk add --no-cache gcc make wget musl-dev build-base

# تنزيل وبناء مكتبة TA-Lib من المصدر
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

WORKDIR /app

# نسخ الملفات المطلوبة وتثبيت المتطلبات
COPY try-with-test-websocket-2.py /app/
COPY requirements.txt /app/

RUN pip install -r requirements.txt

CMD ["python", "try-with-test-websocket-2.py"]
