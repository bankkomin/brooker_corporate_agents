FROM python:3.11-slim

WORKDIR /app

# Install Node.js + mermaid-cli for local mermaid PNG rendering.
# Headless Chromium is required by mermaid-cli (via Puppeteer) for rendering.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg ca-certificates \
    chromium fonts-liberation libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @mermaid-js/mermaid-cli@10 \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && which mmdc

# Write a Puppeteer launch-options config that disables the sandbox
# (mandatory when Chromium runs as root inside Docker) and points to the
# system Chromium installed above instead of the bundled one.
RUN printf '{"executablePath":"/usr/bin/chromium","args":["--no-sandbox","--disable-setuid-sandbox"]}' \
    > /usr/local/etc/puppeteer-config.json

# Replace the bare mmdc symlink with a thin wrapper that always injects
# the puppeteer config. mermaid_render.py calls the path in MERMAID_CLI_PATH
# directly via subprocess so the wrapper is transparent to the caller.
RUN mv /usr/bin/mmdc /usr/bin/mmdc-real \
    && printf '#!/bin/sh\nexec /usr/bin/mmdc-real -p /usr/local/etc/puppeteer-config.json "$@"\n' \
       > /usr/bin/mmdc \
    && chmod +x /usr/bin/mmdc

ENV MERMAID_CLI_PATH=/usr/bin/mmdc
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 3050

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3050"]
