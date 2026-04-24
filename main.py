"""
Service Order - Microsserviço de Pedidos
Responsável por criar e listar pedidos.
Comunica-se de forma ASSÍNCRONA com o service-payment via RabbitMQ.
"""

import json
import uuid
from datetime import datetime

import pika
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Service Order",
    description="Microsserviço responsável por criar e listar pedidos",
    version="1.0.0",
)

# Banco de dados em memória (simulação)
orders_db: dict = {}

RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"
QUEUE_NAME = "payment_queue"


# --- Schemas ---

class OrderCreate(BaseModel):
    customer_name: str
    product: str
    amount: float


class Order(BaseModel):
    id: str
    customer_name: str
    product: str
    amount: float
    status: str
    created_at: str


# --- Helpers ---

def publish_to_queue(message: dict):
    """Publica uma mensagem na fila do RabbitMQ (comunicação assíncrona)."""
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=2),  # mensagem persistente
        )
        connection.close()
        print(f"[Order] Mensagem publicada na fila: {message}")
    except Exception as e:
        print(f"[Order] Erro ao publicar na fila: {e}")
        raise HTTPException(status_code=503, detail="Serviço de mensageria indisponível")


# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "service-order"}


@app.post("/orders", response_model=Order, status_code=201)
def create_order(payload: OrderCreate):
    """
    Cria um novo pedido e publica evento assíncrono para o service-payment processar.
    """
    order_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    order = {
        "id": order_id,
        "customer_name": payload.customer_name,
        "product": payload.product,
        "amount": payload.amount,
        "status": "PENDING",
        "created_at": now,
    }

    # Persiste localmente
    orders_db[order_id] = order

    # Publica evento assíncrono para o service-payment
    publish_to_queue({
        "event": "ORDER_CREATED",
        "order_id": order_id,
        "customer_name": payload.customer_name,
        "amount": payload.amount,
        "timestamp": now,
    })

    return order


@app.get("/orders", response_model=list[Order])
def list_orders():
    """Retorna todos os pedidos."""
    return list(orders_db.values())


@app.get("/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Retorna um pedido específico pelo ID."""
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return order


@app.patch("/orders/{order_id}/status")
def update_order_status(order_id: str, status: str):
    """
    Atualiza o status de um pedido.
    Normalmente chamado pelo service-payment após processar o pagamento.
    """
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    orders_db[order_id]["status"] = status
    return {"message": f"Status do pedido {order_id} atualizado para {status}"}
