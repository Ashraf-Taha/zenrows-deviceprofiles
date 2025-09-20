param(
    [string]$Message
)

if (-not $Message) { $Message = "auto" }
& .\.venv\Scripts\alembic.exe revision --autogenerate -m $Message
