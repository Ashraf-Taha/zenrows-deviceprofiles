$port = if ($env:PORT) { $env:PORT } else { "8080" }
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port $port --reload
