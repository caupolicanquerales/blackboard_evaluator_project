FROM python:3.12-slim
WORKDIR /app

# Unbuffered stdout so stdio MCP messages and logs are not delayed
ENV PYTHONUNBUFFERED=1

# Install fastmcp & dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Execute python script listening on stdio
ENTRYPOINT ["python", "mcp_server.py"]