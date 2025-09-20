$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
if (Test-Path .\.venv\Scripts\python.exe) {
	.\.venv\Scripts\python.exe -m pytest -q
} else {
	pytest -q
}
