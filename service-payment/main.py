"""
Service Payment - Microsserviço de Pagamentos
Responsável por processar pagamentos dos pedidos.
Consome mensagens ASSÍNCRONAS da fila RabbitMQ publicadas pelo service-order.
Após processar, notifica o service-order via HTTP (chamada síncrona de callback).
"""

import json
import random
import threading
import time
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

payments_db: dict = {}

RABBITMQ_URL = "amqp://guest:guest@rabbitmq:5672/"
QUEUE_NAME = "payment_queue"
ORDER_SERVICE_URL = "http://service-order:8000"


class Payment(BaseModel):
    id: str
    order_id: str
    customer_name: str
    amount: float
    status: str
    processed_at: str


def process_payment(order_data: dict) -> dict:
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
    print(f"[Payment] Pagamento processado: {payment_id} → {status}", flush=True)
    return payment


def notify_order_service(order_id: str, status: str):
    try:
        order_status = "PAID" if status == "APPROVED" else "PAYMENT_FAILED"
        response = requests.patch(
            f"{ORDER_SERVICE_URL}/orders/{order_id}/status",
            params={"status": order_status},
            timeout=5,
        )
        print(f"[Payment] Order {order_id} atualizado → {order_status} ({response.status_code})", flush=True)
    except Exception as e:
        print(f"[Payment] Erro ao notificar order service: {e}", flush=True)


def on_message_received(ch, method, properties, body):
    try:
        event = json.loads(body)
        print(f"[Payment] Evento recebido: {event['event']} | Order: {event['order_id']}", flush=True)

        if event.get("event") == "ORDER_CREATED":
            payment = process_payment(event)
            notify_order_service(event["order_id"], payment["status"])

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[Payment] Erro ao processar mensagem: {e}", flush=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def start_consumer():
    """Inicia o consumer com retry automático em caso de falha de conexão."""
    max_retries = 10
    retry_delay = 3

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[Payment] Tentativa {attempt}/{max_retries} de conectar ao RabbitMQ...", flush=True)
            connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message_received)
            print("[Payment] Conectado! Aguardando mensagens na fila...", flush=True)
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            print(f"[Payment] RabbitMQ indisponível: {e}. Aguardando {retry_delay}s...", flush=True)
            time.sleep(retry_delay)

        except Exception as e:
            print(f"[Payment] Erro inesperado no consumer: {e}. Reconectando em {retry_delay}s...", flush=True)
            time.sleep(retry_delay)

    print("[Payment] Nao foi possivel conectar ao RabbitMQ apos todas as tentativas.", flush=True)


@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=start_consumer, daemon=True)
    thread.start()
    print("[Payment] Consumer thread iniciada.", flush=True)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "service-payment"}


@app.get("/payments", response_model=list[Payment])
def list_payments():
    return list(payments_db.values())


@app.get("/payments/{payment_id}", response_model=Payment)
def get_payment(payment_id: str):
    payment = payments_db.get(payment_id)
    if not payment:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")
    return payment