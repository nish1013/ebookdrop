FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends calibre poppler-utils \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pikepdf==10.17.0 pillow==11.3.0
COPY src/ebookdrop/inspection/sandbox_check.py /sandbox/sandbox_check.py
COPY src/ebookdrop/conversion/sandbox_convert.py /sandbox/sandbox_convert.py
USER 65534:65534
ENTRYPOINT ["python", "-I", "-B", "/sandbox/sandbox_check.py"]
