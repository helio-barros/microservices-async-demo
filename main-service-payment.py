"""
Service Payment - Microsserviço de Pagamentos
Responsável por processar pagamentos dos pedidos.
Consome mensagens ASSÍNCRONAS da fila RabbitMQ publicadas pelo service-order.
Após processar, notifica o service-order via HTTP (chamada síncrona de callback).
"""

import json
import random
import threading
from datetime import datetime

import pika
import requests
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Service Payment",
    description="Microsserviço responsável por processar pagamentos dos pedidos",
    version="1.0.0",
)

# Banco de dados em memória (simulação)
payments_db: dict = {}

RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"
QUEUE_NAME = "payment_queue"
ORDER_SERVICE_URL = "http://service-order:8000"


# --- Schemas ---

class Payment(BaseModel):
    id: str
    order_id: str
    customer_name: str
    amount: float
    status: str
    processed_at: str


# --- Processamento Assíncrono ---

def process_payment(order_data: dict) -> dict:
    """
    Simula o processamento de pagamento.
    Em produção: integração com gateway de pagamento (Stripe, PagSeguro, etc.)
    """
    # Simula aprovação com 80% de chance de sucesso
    success = random.random() > 0.2
    status = "APPROVED" if success else "DECLINED"

    payment_id = f"PAY-{order_data['order_id'][:8].upper()}"
    payment = {
        "id": payment_id,
        "order_id": order_data["order_id"],
        "customer_name": order_data["customer_name"],
        "amount": order_data["amount"],
        "status": status,
        "processed_at": datetime.utcnow().isoformat(),
    }

    payments_db[payment_id] = payment
    print(f"[Payment] Pagamento processado: {payment_id} → {status}")
    return payment


def notify_order_service(order_id: str, status: str):
    """
    Notifica o service-order sobre o resultado do pagamento (chamada síncrona REST).
    """
    try:
        order_status = "PAID" if status == "APPROVED" else "PAYMENT_FAILED"
        response = requests.patch(
            f"{ORDER_SERVICE_URL}/orders/{order_id}/status",
            params={"status": order_status},
            timeout=5,
        )
        print(f"[Payment] Order {order_id} atualizado → {order_status} ({response.status_code})")
    except Exception as e:
        print(f"[Payment] Erro ao notificar order service: {e}")


def on_message_received(ch, method, properties, body):
    """Callback chamado ao receber mensagem da fila."""
    try:
        event = json.loads(body)
        print(f"[Payment] Evento recebido: {event['event']} | Order: {event['order_id']}")

        if event.get("event") == "ORDER_CREATED":
            payment = process_payment(event)
            notify_order_service(event["order_id"], payment["status"])

        # Confirma processamento (ACK)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[Payment] Erro ao processar mensagem: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_consumer():
    """Inicia o consumidor RabbitMQ em uma thread separada."""
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message_received)
        print("[Payment] Consumidor aguardando mensagens na fila...")
        channel.start_consuming()
    except Exception as e:
        print(f"[Payment] Erro no consumidor: {e}")


# Inicia consumidor em background ao iniciar o serviço
@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=start_consumer, daemon=True)
    thread.start()
    print("[Payment] Consumer thread iniciada.")


# --- Endpoints ---

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "service-payment"}


@app.get("/payments", response_model=list[Payment])
def list_payments():
    """Retorna todos os pagamentos processados."""
    return list(payments_db.values())


@app.get("/payments/{payment_id}", response_model=Payment)
def get_payment(payment_id: str):
    """Retorna um pagamento específico pelo ID."""
    payment = payments_db.get(payment_id)
    if not payment:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    return payment
