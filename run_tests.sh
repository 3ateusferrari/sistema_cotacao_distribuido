#!/bin/bash

# Cores para o output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Iniciando a execução dos testes...${NC}"

# Função para rodar testes em um serviço
run_service_tests() {
    local service=$1
    echo -e "\n${GREEN}Rodando testes para: $service${NC}"
    # Verifica se o container está rodando, se não, sobe um temporário
    docker-compose run --rm --entrypoint /bin/sh $service -c "pip install pytest pytest-asyncio pytest-mock httpx && pytest tests/"
}

# Unidade e Integração
run_service_tests external_service
run_service_tests quote_service
run_service_tests aggregator_service
run_service_tests client_subscriber

# E2E (Opcional, requer que o sistema esteja rodando)
echo -e "\n${GREEN}Deseja rodar os testes E2E? (Requer docker-compose up) [s/N]${NC}"
# Em um script automatizado poderíamos checar se as portas estão abertas
# Por enquanto, deixaremos o comando aqui para referência
# pytest tests/e2e/test_flow.py

echo -e "\n${GREEN}Testes finalizados!${NC}"
