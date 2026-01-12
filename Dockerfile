# Build Stage for Frontend
FROM node:20-alpine as build-step
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --quiet

COPY . .
RUN npm run build


# Production Stage
FROM python:3.9-slim-bullseye

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-latex-extra \
    texlive-lang-french \
    texlive-pictures \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    texhash && \
    updmap-sys

# Copy Flask App files
COPY app.py ./
COPY CV.tex ./
COPY CoverLetter.tex ./

# Copy compiled frontend from build-step
COPY --from=build-step /app/static/dist ./static/dist

# Create necessary directories
RUN mkdir -p uploads outputs && chmod 777 uploads outputs

# Environment variables
ENV PORT=8080
ENV FLASK_ENV=production

# Run with Gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
