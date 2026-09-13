import requests
import json

# Teste 1: Simular chegada do Webhook CryptoBot confirmando pagamento
url_webhook = "http://localhost:8099/webhook/cryptobot"
payload = {
    "update_id": 1,
    "update_type": "invoice_paid",
    "payload": {
        "invoice_id": 999999,
        "status": "paid",
        "payload": "test_local_order"
    }
}
r = requests.post(url_webhook, json=payload)
print("Teste Webhook CryptoBot local:", r.status_code, r.text)
