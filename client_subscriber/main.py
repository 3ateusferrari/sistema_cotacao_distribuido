import asyncio
import json
import redis.asyncio as redis

# Configuração da Conexão com o Redis
REDIS_URL = "redis://redis_broker:6379"
REDIS_CHANNEL = "precos"

async def price_subscriber():
    """
    Cliente que se conecta ao Redis, assina o canal de preços e
    escuta por novas mensagens de cotação.
    """
    print("--- Cliente Subscriber Iniciado ---")
    print(f"Conectando ao Redis em: {REDIS_URL}")
    print(f"Assinando o canal: '{REDIS_CHANNEL}'")
    
    try:
        # Cria uma conexão com o Redis
        redis_conn = redis.from_url(REDIS_URL, decode_responses=True)
        
        # Cria um objeto PubSub
        pubsub = redis_conn.pubsub()
        
        # Assina o canal
        await pubsub.subscribe(REDIS_CHANNEL)
        
        print("\n--- Aguardando novas cotações ---")
        
        # Loop infinito para escutar por mensagens
        while True:
            # O `listen()` bloqueia até que uma nova mensagem chegue
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
            
            if message and message["type"] == "message":
                # Carrega os dados da mensagem (que estão em formato JSON)
                quote_data = json.loads(message["data"])
                
                # Exibe a cotação recebida de forma formatada
                print("\n++++++++++++++++++++++++++++++++++++++++")
                print(">>> NOVA COTAÇÃO RECEBIDA! <<<")
                print(f"  Bitcoin:  $ {quote_data.get('bitcoin', 0.0):.2f}")
                print(f"  Ethereum: $ {quote_data.get('ethereum', 0.0):.2f}")
                print("++++++++++++++++++++++++++++++++++++++++\n")
            
            await asyncio.sleep(0.1) # Pequeno sleep para não sobrecarregar o loop

    except asyncio.CancelledError:
        print("\nCliente encerrado.")
    except Exception as e:
        print(f"\nOcorreu um erro: {e}")
        print("Tentando reconectar em 10 segundos...")
        await asyncio.sleep(10)
        # Em um cenário real, aqui entraria uma lógica de reconexão mais robusta

if __name__ == "__main__":
    try:
        asyncio.run(price_subscriber())
    except KeyboardInterrupt:
        print("\nPrograma interrompido pelo usuário.")
