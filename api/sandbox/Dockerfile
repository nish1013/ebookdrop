FROM python:3.12-slim
RUN pip install --no-cache-dir pikepdf==10.17.0
COPY src/ebookdrop/inspection/sandbox_check.py /sandbox/sandbox_check.py
USER 65534:65534
ENTRYPOINT ["python", "-I", "-B", "/sandbox/sandbox_check.py"]
