#!/bin/bash
# Script para iniciar PostgreSQL com Docker para ProdPlan ONE

cd "/Users/martimnicolau/nelo final /prodplan-one"

echo "1. Verificando Docker..."
if ! docker ps > /dev/null 2>&1; then
    echo "   Docker não está a correr. A abrir Docker Desktop..."
    open -a Docker
    
    echo "   Aguardar Docker a iniciar (pode demorar 30-60 segundos)..."
    while ! docker ps > /dev/null 2>&1; do
        sleep 2
        echo -n "."
    done
    echo ""
    echo "   ✓ Docker está pronto!"
else
    echo "   ✓ Docker já está a correr"
fi

echo ""
echo "2. Verificando PostgreSQL container..."
if docker ps -a | grep -q prodplan-postgres; then
    if docker ps | grep -q prodplan-postgres; then
        echo "   ✓ PostgreSQL já está a correr"
    else
        echo "   Iniciando container existente..."
        docker start prodplan-postgres
        sleep 5
    fi
else
    echo "   Criando novo container PostgreSQL..."
    docker run -d \
      --name prodplan-postgres \
      -e POSTGRES_USER=prodplan \
      -e POSTGRES_PASSWORD=prodplan_secret_2026 \
      -e POSTGRES_DB=prodplan_one \
      -p 5432:5432 \
      postgres:14
    
    echo "   Aguardar inicialização (15 segundos)..."
    sleep 15
fi

echo ""
echo "3. Verificando conexão..."
if docker ps | grep -q prodplan-postgres; then
    echo "   ✓ Container está a correr"
    
    echo ""
    echo "4. Testando backend..."
    curl -s http://localhost:8000/health/ready | python3 -m json.tool 2>/dev/null || \
        echo "   Backend não está a correr. Inicie com: python3 -m src.main"
else
    echo "   ✗ Container não está a correr. Ver logs:"
    echo "   docker logs prodplan-postgres"
fi

echo ""
echo "Concluído!"
