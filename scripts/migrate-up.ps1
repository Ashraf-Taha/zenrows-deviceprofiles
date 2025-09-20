param(
    [string]$DatabaseUrl
)

if (-not $DatabaseUrl) {
    $host = $env:DB_HOST
    if (-not $host) { $host = "localhost" }
    $port = $env:DB_PORT
    if (-not $port) { $port = "5432" }
    $db = $env:DB_NAME
    if (-not $db) { $db = "zenrows" }
    $user = $env:DB_USER
    if (-not $user) { $user = "postgres" }
    $pwd = $env:DB_PASSWORD
    if (-not $pwd) { $pwd = "postgres" }
    $DatabaseUrl = "postgresql+psycopg://$user:$pwd@$host:$port/$db"
}

$env:DATABASE_URL = $DatabaseUrl
& .\.venv\Scripts\alembic.exe upgrade head