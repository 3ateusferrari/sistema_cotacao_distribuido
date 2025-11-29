import asyncio
import random
from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="Serviço Externo de Cotações",
    description="Simula um serviço que fornece cotações de criptomoedas e pode falhar.",
    version="1.0.0",
)

# Estado interno para simular a variação das cotações
current_prices = {
    "bitcoin": 50000.0,
    "ethereum": 3000.0,
}

# Configuração de falha
# O serviço irá falhar em 30% das requisições
FAILURE_RATE = 0.3

async def update_prices():
    """
    Atualiza os preços em segundo plano para simular um mercado em tempo real.
    """
    while True:
        await asyncio.sleep(5)  # Atualiza a cada 5 segundos
        for coin in current_prices:
            # Variação de -1% a +1%
            change_percent = random.uniform(-0.01, 0.01)
            current_prices[coin] *= 1 + change_percent
        print(f"Preços atualizados: {current_prices}")

@app.on_event("startup")
async def startup_event():
    """
    Inicia a tarefa de atualização de preços quando o servidor é iniciado.
    """
    asyncio.create_task(update_prices())

@app.get("/quote")
async def get_quote():
    """
    Endpoint que retorna a cotação atual.
    Pode falhar intencionalmente para testar a resiliência do sistema.
    """
    if random.random() < FAILURE_RATE:
        print("-> Falha simulada no serviço externo!")
        raise HTTPException(
            status_code=503,
            detail="Serviço indisponível. Tente novamente mais tarde.",
        )

    print(f"-> Cotação solicitada com sucesso: {current_prices}")
    return current_prices
