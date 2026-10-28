# SNOWMAN Base i Docker (NAS: Synology Container Manager, QNAP Container Station, eller vanleg Docker).
# Programmet ligg i ei mappe som blir montert inn (/app) – då fungerer «Oppdater» på kontorsida som på PC.
FROM python:3.12-slim
RUN pip install --no-cache-dir pyserial
ENV SNOWMAN_BASE_TENESTE=1 SNOWMAN_BASE_DATA=/data PYTHONUNBUFFERED=1
WORKDIR /app
EXPOSE 2101 8780
VOLUME ["/data"]
CMD ["python", "/app/snowman_base.py"]
