# 🚀 microservices-async-demo

Projeto prático desenvolvido como parte da **Fase 1 - Aula 4** da pós-graduação POSTECH (DevOps e Arquitetura Cloud).

Demonstra arquitetura assíncrona entre microsserviços utilizando **FastAPI** e **RabbitMQ**, aplicando os conceitos de comunicação síncrona e assíncrona estudados em aula.

---

## 📐 Arquitetura

```
┌─────────────┐    POST /orders     ┌───────────────┐
│   Cliente   │ ─────────────────► │ service-order │
│  (HTTP)     │                     │  (porta 8000) │
└─────────────┘                     └───────┬───────┘
                                            │
                                   Publica evento
                                   ORDER_CREATED
                                            │
                                            ▼
                                    ┌──────────────┐
                                    │   RabbitMQ   │
                                    │ payment_queue│
                                    └──────┬───────┘
                                           │
                                  Consome mensagem
                                           │
                                           ▼
                                  ┌─────────────────┐
                                  │ service-payment │
                                  │  (porta 8001)   │
                                  └────────┬────────┘
                                           │
                                  PATCH /orders/{id}/status
                                  (notificação síncrona)
                                           │
                                           ▼
                                  ┌────────────────┐
                                  │ service-order  │
                                  │ Status: PAID / │
                                  │ PAYMENT_FAILED │
                                  └────────────────┘
```

---

## 🧩 Microsserviços

### `service-order` — Gerenciamento de Pedidos
- **Porta:** `8000`
- **Responsabilidade:** Criar e listar pedidos
- **Comunicação:**
  - Expõe API REST síncrona para o cliente
  - Publica evento `ORDER_CREATED` de forma **assíncrona** no RabbitMQ

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/orders` | Cria um novo pedido |
| `GET` | `/orders` | Lista todos os pedidos |
| `GET` | `/orders/{id}` | Retorna um pedido específico |
| `PATCH` | `/orders/{id}/status` | Atualiza status do pedido |
| `GET` | `/health` | Health check |

---

### `service-payment` — Processamento de Pagamentos
- **Porta:** `8001`
- **Responsabilidade:** Processar pagamentos dos pedidos
- **Comunicação:**
  - Consome mensagens da fila `payment_queue` de forma **assíncrona**
  - Notifica o `service-order` via PATCH HTTP após processar

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/payments` | Lista todos os pagamentos |
| `GET` | `/payments/{id}` | Retorna um pagamento específico |
| `GET` | `/health` | Health check |

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Uso |
|------------|-----|
| **Python 3.11** | Linguagem principal |
| **FastAPI** | Framework web para APIs REST |
| **RabbitMQ** | Broker de mensagens (comunicação assíncrona) |
| **Pika** | Cliente Python para RabbitMQ |
| **Docker / Docker Compose** | Containerização e orquestração |
| **Uvicorn** | Servidor ASGI para FastAPI |

---

## 📁 Estrutura do Repositório

```
microservices-async-demo/
├── docker-compose.yml          # Orquestração dos serviços
├── README.md
│
├── service-order/
│   ├── main.py                 # API FastAPI + publisher RabbitMQ
│   ├── requirements.txt
│   └── Dockerfile
│
└── service-payment/
    ├── main.py                 # API FastAPI + consumer RabbitMQ
    ├── requirements.txt
    └── Dockerfile
```

---

## ▶️ Como Executar

### Pré-requisitos
- Docker e Docker Compose instalados

### 1. Clone o repositório
```bash
git clone https://github.com/seu-usuario/microservices-async-demo.git
cd microservices-async-demo
```

### 2. Suba todos os serviços
```bash
docker compose up --build
```

### 3. Acesse os serviços

| Serviço | URL |
|---------|-----|
| service-order (API) | http://localhost:8000/docs |
| service-payment (API) | http://localhost:8001/docs |
| RabbitMQ Management | http://localhost:15672 (guest/guest) |

---

## 🧪 Testando o Fluxo Completo

### Criar um pedido (service-order)
```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "João Silva",
    "product": "Notebook",
    "amount": 3500.00
  }'
```

### Listar pedidos e verificar status
```bash
curl http://localhost:8000/orders
```

### Listar pagamentos processados
```bash
curl http://localhost:8001/payments
```

---

## 💡 Conceitos Aplicados (Aula 4)

- **Comunicação Assíncrona:** O `service-order` não aguarda o processamento do pagamento. Publica o evento e segue disponível.
- **Desacoplamento Temporal:** Os serviços operam independentemente; se o `service-payment` estiver fora, as mensagens ficam na fila.
- **Mensageria com RabbitMQ:** Uso de filas duráveis com ACK/NACK para garantia de entrega.
- **Comunicação Síncrona (callback):** Após processar, o `service-payment` notifica o `service-order` via REST.
- **Padrão Híbrido:** Combinação de REST (síncrono) para o cliente + eventos (assíncrono) internamente — tendência destacada na aula.

---

## 👤 Autor

Desenvolvido por **Hélio Judson** como atividade prática da POSTECH — DevOps e Arquitetura Cloud.
