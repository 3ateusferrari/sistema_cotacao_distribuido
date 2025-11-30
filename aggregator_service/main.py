import asyncio
import httpx
from fastapi import FastAPI, HTTPException
from databases import Database

# Configuração da Aplicação
app = FastAPI(
    title="Serviço Agregador (Scatter/Gather)",
    description="Orquestra chamadas a múltiplos serviços para compor uma resposta complexa.",
    version="1.0.0",
)

# Configurações de Conexão
QUOTE_SERVICE_URL = "http://quote_service:8000"
SHARD1_DATABASE_URL = "postgresql://shard1:shard1pass@shard1_db:5432/logs"
SHARD2_DATABASE_URL = "postgresql://shard2:shard2pass@shard2_db:5432/logs"

# Conexões com os Shards do Banco de Dados
shard1_db = Database(SHARD1_DATABASE_URL)
shard2_db = Database(SHARD2_DATABASE_URL)

# --- Funções do Agregador (Scatter) ---

async def fetch_current_average_price(client: httpx.AsyncClient, coin: str):
    """
    Busca a média de preço atual do serviço de cotação.
    """
    try:
        response = await client.get(f"{QUOTE_SERVICE_URL}/media_ultimos_10_logs/{coin}")
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        print(f"Erro ao buscar média de {coin}: {e}")
        return {"error": f"Não foi possível obter a média para {coin}"}

async def fetch_last_logs_from_shard(db: Database, coin: str, limit: int = 5):
    """
    Busca os últimos logs de um shard específico.
    """
    query = "SELECT coin, price, timestamp FROM quote_logs WHERE coin = :coin ORDER BY timestamp DESC LIMIT :limit"
    try:
        results = await db.fetch_all(query=query, values={"coin": coin, "limit": limit})
        # Converte os resultados para um formato serializável em JSON
        return [
            {
                "coin": row["coin"],
                "price": row["price"],
                "timestamp": row["timestamp"].isoformat(),
            }
            for row in results
        ]
    except Exception as e:
        print(f"Erro ao buscar logs de {coin} no shard: {e}")
        return [{"error": f"Não foi possível obter logs para {coin}"}]


# --- Eventos de Ciclo de Vida ---

@app.on_event("startup")
async def startup_event():
    await shard1_db.connect()
    await shard2_db.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await shard1_db.disconnect()
    await shard2_db.disconnect()

# --- Endpoint Principal (Gather) ---

@app.get("/report/full")
async def get_full_report():
    """
    Endpoint que aplica o padrão Scatter/Gather para construir um relatório completo.
    
    Ele busca em paralelo:
    1. Média de preço do Bitcoin (do `quote_service`).
    2. Média de preço do Ethereum (do `quote_service`).
    3. Últimos 5 logs de Bitcoin (do `shard1`).
    4. Últimos 5 logs de Ethereum (do `shard2`).
    
    E então, agrega tudo em uma única resposta.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Scatter: Dispara todas as requisições em paralelo
        tasks = [
            fetch_current_average_price(client, "bitcoin"),
            fetch_current_average_price(client, "ethereum"),
            fetch_last_logs_from_shard(shard1_db, "bitcoin"),
            fetch_last_logs_from_shard(shard2_db, "ethereum"),
        ]
        
        # Gather: Aguarda a conclusão de todas as tarefas
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Mapeia os resultados para evitar erros se alguma tarefa falhar
        avg_btc, avg_eth, logs_btc, logs_eth = results

    # Helper para extrair a média de forma segura
    def get_avg(result):
        if isinstance(result, Exception) or not isinstance(result, dict):
            return "Erro"
        return result.get("average_price", "Chave 'average_price' não encontrada")

    # Composição da resposta final
    response_data = {
        "media_precos": {
            "bitcoin": get_avg(avg_btc),
            "ethereum": get_avg(avg_eth),
        },
        "ultimos_logs": {
            "bitcoin": logs_btc if not isinstance(logs_btc, Exception) else "Erro",
            "ethereum": logs_eth if not isinstance(logs_eth, Exception) else "Erro",
        }
    }

    return response_data
