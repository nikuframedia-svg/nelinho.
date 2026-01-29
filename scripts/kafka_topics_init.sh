#!/bin/bash
# Kafka Topics Initialization Script
# Creates required topics for ProdPlan ONE event-driven architecture

KAFKA_BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP_SERVER:-localhost:29092}"

echo "Creating Kafka topics for ProdPlan ONE..."
echo "Bootstrap server: $KAFKA_BOOTSTRAP_SERVER"

# Topics to create
TOPICS=(
    "prodplan.plan.schedule.committed"
    "prodplan.inventory.movement"
    "prodplan.quality.gate.passed"
    "prodplan.copilot.action.executed"
    "prodplan.dlq"
)

for topic in "${TOPICS[@]}"; do
    echo "Creating topic: $topic"
    kafka-topics --create \
        --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" \
        --topic "$topic" \
        --partitions 3 \
        --replication-factor 1 \
        --if-not-exists \
        || echo "Topic $topic already exists or failed to create"
done

echo "Kafka topics initialization complete!"










