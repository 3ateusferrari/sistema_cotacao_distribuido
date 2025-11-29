import asyncio
import json
from datetime import datetime
import asyncpg
import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from databases import Database

# Configuração da Aplicação
app = FastAPI(
    title="Serviço de Cotação Primário",
    description="Componente central que gerencia cotações, publicações e armazenamento.",
    version="1.0.0",
)

# Configurações de Conexão
REDIS_URL = "redis://redis_broker:6379"
EXTERNAL_SERVICE_URL = "http://external_service:8000/quote"
SHARD1_DATABASE_URL = "postgresql://shard1:shard1pass@shard1_db:5432/logs"
SHARD2_DATABASE_URL = "postgresql://shard2:shard2pass@shard2_db:5432/logs"

# Pool de Conexões com o Redis
redis_pool = redis.from_url(REDIS_URL, decode_responses=True)

# Conexões com os Shards do Banco de Dados
shard1_db = Database(SHARD1_DATABASE_URL)
shard2_db = Database(SHARD2_DATABASE_URL)

# Estado para armazenar o último valor bem-sucedido (cache para o Circuit Breaker)
last_known_quote = {"bitcoin": 0.0, "ethereum": 0.0}

# --- Funções do Núcleo ---

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    retry_error_callback=lambda _: last_known_quote  # Retorna o cache se todas as tentativas falharem
)
async def fetch_quote_from_external_service():
    """
    Busca a cotação do serviço externo com um Circuit Breaker (via Tenacity).
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(EXTERNAL_SERVICE_URL)
        response.raise_for_status()  # Lança exceção para códigos de erro HTTP
        new_quote = response.json()
        
        # Atualiza o cache global se a chamada for bem-sucedida
        global last_known_quote
        last_known_quote = new_quote
        
        print(f"Cotação externa obtida com sucesso: {new_quote}")
        return new_quote

async def store_log(coin: str, price: float):
    """
    Armazena o log da cotação no shard apropriado.
    """
    timestamp = datetime.utcnow()
    
    if coin == "bitcoin":
        db = shard1_db
    elif coin == "ethereum":
        db = shard2_db
    else:
        return  # Não armazena logs para outras moedas

    query = "INSERT INTO quote_logs (coin, price, timestamp) VALUES (:coin, :price, :timestamp)"
    values = {"coin": coin, "price": price, "timestamp": timestamp}
    
    try:
        await db.execute(query=query, values=values)
        print(f"Log armazenado para {coin} no {db.url.database}")
    except Exception as e:
        print(f"Erro ao armazenar log para {coin}: {e}")

async def background_quote_updater():
    """
    Tarefa em segundo plano que periodicamente busca, publica e armazena cotações.
    """
    while True:
        await asyncio.sleep(10)  # Intervalo de 10 segundos
        
        print("--- Iniciando ciclo de atualização de cotações ---")
        
        # 1. Buscar cotação (com Circuit Breaker)
        quote = await fetch_quote_from_external_service()
        
        if not quote or quote == last_known_quote and all(v == 0 for v in last_known_quote.values()):
            print("Não foi possível obter a cotação. Usando valor cacheado ou inicial.")
            continue

        # 2. Publicar no Redis (Pub/Sub)
        await redis_pool.publish("precos", json.dumps(quote))
        print(f"Cotação publicada no canal 'precos': {quote}")
        
        # 3. Armazenar Logs (Sharding)
        await store_log("bitcoin", quote.get("bitcoin", 0.0))
        await store_log("ethereum", quote.get("ethereum", 0.0))
        
        print("--- Ciclo de atualização finalizado ---")



# --- Funções de Banco de Dados ---

async def create_tables():
    """
    Cria as tabelas nos shards se elas não existirem.
    """
    create_table_query = """
    CREATE TABLE IF NOT EXISTS quote_logs (
        id SERIAL PRIMARY KEY,
        coin VARCHAR(10) NOT NULL,
        price FLOAT NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL
    );
    """
    try:
        await shard1_db.execute(create_table_query)
        print("Tabela 'quote_logs' verificada/criada no shard 1.")
        await shard2_db.execute(create_table_query)
        print("Tabela 'quote_logs' verificada/criada no shard 2.")
    except Exception as e:
        print(f"Erro ao criar tabelas: {e}")

# --- Eventos de Ciclo de Vida da Aplicação ---

@app.on_event("startup")
async def startup_event():
    """
    Conecta aos bancos de dados e inicia a tarefa de atualização.
    """
    await shard1_db.connect()
    await shard2_db.connect()
    await create_tables()  # Garante que as tabelas existam
    asyncio.create_task(background_quote_updater())

@app.on_event("shutdown")
async def shutdown_event():
    """
    Desconecta dos bancos de dados.
    """
    await shard1_db.disconnect()
    await shard2_db.disconnect()

# --- Endpoints da API ---

@app.get("/cotacao_atual/{coin}")
async def get_current_quote(coin: str):
    """
    Retorna a cotação mais recente conhecida para uma moeda específica.
    """
    if coin.lower() not in last_known_quote:
        raise HTTPException(status_code=404, detail="Moeda não encontrada.")
    
    return {"coin": coin, "price": last_known_quote[coin.lower()]}

@app.get("/media_ultimos_10_logs/{coin}")
async def get_average_last_10(coin: str):
    """
    Calcula e retorna a média dos últimos 10 logs de uma moeda do shard correspondente.
    """
    if coin.lower() == "bitcoin":
        db = shard1_db
    elif coin.lower() == "ethereum":
        db = shard2_db
    else:
        raise HTTPException(status_code=404, detail="Moeda não suportada para logs.")

    query = "SELECT price FROM quote_logs WHERE coin = :coin ORDER BY timestamp DESC LIMIT 10"
    results = await db.fetch_all(query=query, values={"coin": coin.lower()})

    if not results:
        return {"coin": coin, "average_price": 0, "log_count": 0}

    total_price = sum(row["price"] for row in results)
    average_price = total_price / len(results)

    return {"coin": coin, "average_price": average_price, "log_count": len(results)}
