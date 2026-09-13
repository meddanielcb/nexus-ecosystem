#!/usr/bin/env python3
"""
Supervisor / Watchdog autônomo para o Nexus Tools Store Bot.
Monitora run_store.py e webhook_server.py 24/7.
Se qualquer um cair ou a máquina reiniciar, reinicia imediatamente.
"""

import subprocess
import time
import sys
import os
import signal
import socket
from notifier import alert_system

PYTHON_BIN = "/opt/hermes/.venv/bin/python3"
BASE_DIR = "/opt/data/digital_store_bot"

# Trava de instância única do supervisor para evitar processos duplicados
LOCK_SOCKET = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
try:
    LOCK_SOCKET.bind('\0nexus_supervisor_lock')
except socket.error:
    print("Supervisor já está rodando em outro processo. Encerrando esta instância.")
    sys.exit(0)

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

SERVICES = {
    "webhook_server": os.path.join(BASE_DIR, "webhook_server.py"),
    "run_store": os.path.join(BASE_DIR, "run_store.py"),
    "run_playtv": "/opt/data/nexus_playtv_bot/run_playtv.py"
}

processes = {}

def start_service(name, script_path):
    # Se for webhook_server e a porta já estiver em uso, aguarda liberar para evitar crash-loop
    if name == "webhook_server" and is_port_in_use(8099):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Porta 8099 ocupada. Aguardando liberação para {name}...")
        for _ in range(10):
            time.sleep(1)
            if not is_port_in_use(8099):
                break
        if is_port_in_use(8099):
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] AVISO: Porta 8099 segue ocupada por outra instância.")

    log_file = os.path.join(BASE_DIR, "logs", f"{name}.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    f = open(log_file, "a")
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando {name}...")
    p = subprocess.Popen(
        [PYTHON_BIN, script_path],
        cwd=BASE_DIR,
        stdout=f,
        stderr=subprocess.STDOUT
    )
    return p

def cleanup(signum, frame):
    print("\nEncerrando supervisor e subprocessos...")
    for name, p in processes.items():
        if p and p.poll() is None:
            p.terminate()
    sys.exit(0)

signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

print("=== Nexus Tools Supervisor Iniciado ===")
for name, script in SERVICES.items():
    processes[name] = start_service(name, script)

while True:
    time.sleep(5)
    for name, script in SERVICES.items():
        p = processes.get(name)
        if p is None or p.poll() is not None:
            code = p.poll() if p else "None"
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] AVISO: {name} parou (exit code: {code}). Reiniciando...")
            # Enviar alerta apenas se for queda anormal (exit code != 0, -15, -9)
            # -15 (SIGTERM) e -9 (SIGKILL) ocorrem durante reload intencional / deploys
            is_abnormal = code not in (0, -15, -9, None)
            if is_abnormal:
                try:
                    alert_system(
                        event_type=f"Falha de Processo: {name}",
                        details=f"O serviço parou inesperadamente com exit code `{code}`. Supervisor reiniciou o processo automaticamente."
                    )
                except Exception:
                    pass
            processes[name] = start_service(name, script)
            
            # Aguarda inicialização e envia confirmação de recuperação apenas se houve alerta de falha
            time.sleep(2)
            new_p = processes.get(name)
            if is_abnormal and new_p and new_p.poll() is None:
                try:
                    alert_system(
                        event_type=f"Recuperado com Sucesso: {name}",
                        details=f"O processo `{name}` foi reiniciado com sucesso (PID `{new_p.pid}`) e está operacional."
                    )
                except Exception:
                    pass
