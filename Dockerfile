FROM python:3.14-slim

WORKDIR /app

COPY environment.yml ./
RUN pip install --no-cache-dir \
    fastapi==0.135.3 \
    uvicorn[standard]==0.34.3 \
    authlib==1.4.1 \
    httpx==0.28.1 \
    python-jose[cryptography]==3.3.0 \
    python-dotenv==1.1.0 \
    itsdangerous==2.2.0

COPY main.py ./

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
