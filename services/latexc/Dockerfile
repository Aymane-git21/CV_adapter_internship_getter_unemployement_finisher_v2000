# latexc: warm sandboxed XeLaTeX compile service.
# Build context is the REPO ROOT (needs templates/typst/fonts):
#   docker build -f services/latexc/Dockerfile .
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-xetex texlive-latex-recommended texlive-fonts-recommended \
    latexmk poppler-utils fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Same font files the Typst preview uses -> identical glyphs in both compilers.
COPY templates/typst/fonts /usr/local/share/fonts/cvglowup
RUN fc-cache -f

WORKDIR /srv
COPY services/latexc/requirements.txt latexc/requirements.txt
RUN pip install --no-cache-dir -r latexc/requirements.txt
COPY services/latexc/ latexc/

RUN useradd --create-home texuser && mkdir -p /tmp/compiles && chown -R texuser /tmp/compiles
USER texuser
ENV PORT=8080 COMPILE_ROOT=/tmp/compiles PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["sh", "-c", "uvicorn latexc.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
