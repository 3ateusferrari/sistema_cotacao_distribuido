# Sistema de Cotações Distribuído

Este projeto implementa um sistema de cotações de criptomoedas em tempo real, construído com uma arquitetura de microsserviços e aplicando padrões de projeto distribuídos.

## Arquitetura

O sistema é composto por quatro serviços principais que se comunicam de forma assíncrona e resiliente:

- **Servidor Externo (`external_service`):** Simula uma fonte de dados externa que gera cotações de criptomoedas (Bitcoin e Ethereum). Este serviço foi projetado para ser instável, falhando propositalmente em algumas requisições para testar a resiliência do sistema.

- **Serviço de Cotação (`quote_service`):** O núcleo do sistema. Ele é responsável por:
    - Buscar as cotações do serviço externo, protegido por um **Circuit Breaker**.
    - Publicar as novas cotações em um canal do Redis, utilizando o padrão **Pub/Sub**.
    - Armazenar o histórico de cotações em bancos de dados PostgreSQL, aplicando o padrão de **Sharding**.

- **Serviço Agregador (`aggregator_service`):** Responsável por orquestrar consultas complexas que envolvem múltiplos serviços. Ele utiliza o padrão **Scatter/Gather** para buscar dados em paralelo do `quote_service` e dos shards do banco de dados.

- **Cliente Subscriber (`client_subscriber`):** Um cliente que se inscreve no canal do Redis para receber as atualizações de cotação em tempo real.

### Diagrama da Arquitetura

```
+------------------+      +---------------------+      +-------------------+
| External Service | <--- |    Quote Service    | ---> |   Redis Pub/Sub   |
+------------------+      +---------------------+      +-------------------+
       ^   |                     |     ^                      |
       |   |                     |     |                      v
       |   +---------------------+     |              +-------------------+
       |                               |              | Client Subscriber |
       +-------------------------------+              +-------------------+

+---------------------+      +---------------------+
|      Shard 1        | <--- |    Quote Service    |
| (PostgreSQL - BTC)  |      +---------------------+
+---------------------+      
                             
+---------------------+      +---------------------+
|      Shard 2        | <--- |    Quote Service    |
| (PostgreSQL - ETH)  |      +---------------------+
+---------------------+      

+----------------------+      +---------------------+
| Aggregator Service   | ---> |    Quote Service    |
+----------------------+      +---------------------+
           |
           |                  +---------------------+
           +--------------- > |      Shard 1        |
           |                  +---------------------+
           |
           |                  +---------------------+
           +--------------- > |      Shard 2        |
                              +---------------------+
```

## Padrões de Projeto Distribuídos

- **Circuit Breaker:** Implementado no `quote_service` com a biblioteca `tenacity`. Quando o `external_service` falha repetidamente, o circuito "abre" e o `quote_service` para de fazer novas requisições por um tempo, retornando um valor de cache. Isso evita falhas em cascata e aumenta a resiliência do sistema.

- **Pub/Sub (Publish/Subscribe):** O `quote_service` publica as atualizações de cotação em um canal do Redis. Os `client_subscriber`s podem se inscrever nesse canal para receber as atualizações em tempo real, sem a necessidade de polling. Isso desacopla os produtores dos consumidores e permite uma comunicação assíncrona e escalável.

- **Sharding:** O histórico de cotações é particionado (sharded) em dois bancos de dados PostgreSQL. O `shard1` armazena os logs de Bitcoin e o `shard2` os de Ethereum. Isso distribui a carga de escrita e leitura, melhora a latência das consultas e aumenta a escalabilidade e disponibilidade do banco de dados.

- **Scatter/Gather:** O `aggregator_service` implementa este padrão para responder a consultas complexas. Ele envia requisições em paralelo para o `quote_service` e para os shards do banco de dados, e então agrega os resultados em uma única resposta. Isso otimiza o tempo de resposta para consultas que dependem de múltiplas fontes de dados.

## Tecnologias Utilizadas

- **Python 3.14.0**
- **FastAPI:** Para a construção dos microsserviços.
- **HTTPx:** Para a comunicação HTTP assíncrona entre os serviços.
- **Tenacity:** Para a implementação do padrão Circuit Breaker.
- **Redis:** Como broker de mensagens para o padrão Pub/Sub.
- **PostgreSQL:** Como banco de dados para o armazenamento do histórico de cotações.
- **Asyncpg:** Driver assíncrono para o PostgreSQL.
- **Docker e Docker Compose:** Para a orquestração dos contêineres.

## Como Executar o Projeto

1.  **Pré-requisitos:**
    -   Docker
    -   Docker Compose

2.  **Clone o repositório:**
    ```bash
    git clone <url-do-repositorio>
    cd sistema_cotacao_distribuido
    ```

3.  **Inicie os serviços com Docker Compose:**
    ```bash
    docker-compose up --build
    ```

    Este comando irá construir as imagens dos contêineres e iniciar todos os serviços.

## Serviços

### External Service
- **URL:** `http://localhost:8001`
- **Endpoint:**
    - `GET /quote`: Retorna a cotação atual de Bitcoin and Ethereum.

### Quote Service
- **URL:** `http://localhost:8002`
- **Endpoints:**
    - `GET /cotacao_atual/{coin}`: Retorna a cotação mais recente de uma moeda (`bitcoin` ou `ethereum`).
    - `GET /media_ultimos_10_logs/{coin}`: Retorna a média dos últimos 10 logs de uma moeda.

### Aggregator Service
- **URL:** `http://localhost:8003`
- **Endpoint:**
    - `GET /report/full`: Retorna um relatório completo com a média de preços e os últimos logs de Bitcoin e Ethereum.

### Client Subscriber
- Este serviço não possui endpoints. Ele se conecta ao Redis e imprime as atualizações de cotação no console. Você pode ver os logs do container para acompanhar as atualizações em tempo real:
    ```bash
    docker logs -f client_subscriber
    ```
