import http.client
import json
import urllib.parse
import time
import os
from datetime import datetime
from flask import Flask, request

app = Flask(__name__)

# Variáveis globais com token e api_key do ambiente
token = os.getenv("TELEGRAM_TOKEN")
api_key = os.getenv("API_KEY")

if not token or not api_key:
    raise ValueError("Configure as variáveis TELEGRAM_TOKEN e API_KEY no ambiente")

def envia_telegram(texto, chat_id):
    conn = http.client.HTTPSConnection("api.telegram.org")
    texto_url = urllib.parse.quote_plus(texto)
    endpoint = f"/bot{token}/sendMessage?chat_id={chat_id}&text={texto_url}&parse_mode=Markdown"
    conn.request("GET", endpoint)
    res = conn.getresponse()
    res.read()
    conn.close()

def pega_mensagens(offset=0):
    conn = http.client.HTTPSConnection("api.telegram.org")
    params = f"?offset={offset}" if offset else ""
    endpoint = f"/bot{token}/getUpdates{params}"
    conn.request("GET", endpoint)
    res = conn.getresponse()
    data = res.read().decode("utf-8")
    conn.close()

    try:
        response = json.loads(data)
        if "result" not in response:
            print("⚠️ Resposta da API sem 'result':", response)
            return {"result": []}
        return response
    except Exception as e:
        print("Erro ao carregar updates:", e)
        print("Resposta crua da API:", data)
        return {"result": []}

def parse_custom_date(date_str):
    # Transforma ddmmaa ou ddmmaaaa em yyyy-mm-dd
    if len(date_str) == 6:
        day = date_str[:2]
        month = date_str[2:4]
        year = '20' + date_str[4:]
        full_date = f"{day}{month}{year}"
    elif len(date_str) == 8:
        full_date = date_str
    else:
        raise ValueError("Formato de data inválido. Use ddmmaa ou ddmmaaaa.")
    return datetime.strptime(full_date, "%d%m%Y").strftime("%Y-%m-%d")

def requisita_api(parametros_sem_horas):
    # parâmetros_sem_horas = 'ORIGEM;DESTINO;DATAPARTIDA;DATARETORNO;PRECOMIN;PRECOMAX'
    try:
        from_, to_, departure_date_raw, return_date_raw, price_min, price_max = parametros_sem_horas.split(';')
        departure_date = parse_custom_date(departure_date_raw)
        return_date = parse_custom_date(return_date_raw)
        price_min = float(price_min)
        price_max = float(price_max)

        conn = http.client.HTTPSConnection("booking-com.p.rapidapi.com")
        headers = {
            'x-rapidapi-key': api_key,
            'x-rapidapi-host': "booking-com.p.rapidapi.com"
        }
        url = (
            f"/v1/flights/search?from_code={from_}.AIRPORT"
            f"&to_code={to_}.AIRPORT"
            f"&depart_date={departure_date}"
            f"&return_date={return_date}"
            f"&page_number=1"
            f"&currency=BRL"
            f"&children_ages=0"
            f"&adults=1"
            f"&cabin_class=ECONOMY"
            f"&locale=pt-br"
            f"&flight_type=ROUNDTRIP"
            f"&order_by=CHEAPEST"
        )
        conn.request("GET", url, headers=headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        conn.close()

        api_dict = json.loads(data)
        flight_offers = api_dict.get('flightOffers', [])

        if not flight_offers:
            return "Nenhuma oferta de voo encontrada."

        offer = flight_offers[0]
        price_info = offer.get('priceBreakdown', {})
        price_total_info = price_info.get('total', {})
        price_base_info = price_info.get('baseFare', {})

        price_total = price_total_info.get('units', 0) + price_total_info.get('nanos', 0) / 1e9
        price_base = price_base_info.get('units', 0) + price_base_info.get('nanos', 0) / 1e9

        if price_min < price_base < price_max:
            return f"💰 Oferta encontrada!\nPreço base (sem taxas): R$ {price_base:.2f}\nPreço total (com taxas): R$ {price_total:.2f}"
        else:
            return "Nenhum voo dentro da faixa de preço informada."

    except Exception as e:
        return f"Erro ao consultar API: {e}"

def loop_telegram():
    atual = 0
    chats_respondidos = set()

    while True:
        updates = pega_mensagens(atual)
        for resultado in updates["result"]:
            atual = resultado["update_id"] + 1
            mensagem = resultado.get("message")
            if not mensagem:
                continue

            text = mensagem.get("text", "")
            cid = mensagem["chat"]["id"]
            first_name = mensagem["chat"].get("first_name", "usuário")

            # Primeira interação: envia instruções e formulário
            if cid not in chats_respondidos:
                mensagem1 = f"Olá {first_name} ✈️\nPor favor, preencha o formulário abaixo:"
                mensagem2 = (
                    "Local de partida: \n"
                    "Local de chegada: \n"
                    "Data de Partida: \n"
                    "Data de retorno: \n"
                    "Valor mínimo da passagem: \n"
                    "Valor máximo da passagem: \n"
                    "Horas de execução do serviço:"
                )
                envia_telegram(mensagem1, cid)
                envia_telegram(mensagem2, cid)
                chats_respondidos.add(cid)
                continue

            # Verifica se o texto tem todos os campos do formulário
            if all(campo in text for campo in [
                "Local de partida:", "Local de chegada:", "Data de Partida:",
                "Data de retorno:", "Valor mínimo da passagem:",
                "Valor máximo da passagem:", "Horas de execução do serviço:"
            ]):
                try:
                    linhas = text.split('\n')
                    valores = [linha.split(':', 1)[1].strip().upper() for linha in linhas if ':' in linha]
                    if len(valores) == 7:
                        parametros_str = ';'.join(valores[:6])
                        horas = int(valores[6])

                        envia_telegram(f"Buscando voos por {horas} hora(s)...\nPara cancelar digite 'para'", cid)

                        interrompe = False
                        for h in range(horas):
                            envia_telegram(f"🔎 Verificação {h+1}/{horas} em andamento...", cid)
                            resposta = requisita_api(parametros_str)
                            envia_telegram(resposta, cid)
                            print(resposta)

                            if h < horas - 1:
                                tempo_total = 3600  # 1 hora
                                intervalo = 5      # intervalo de checagem para mensagens em segundos
                                ciclos = tempo_total // intervalo

                                for _ in range(ciclos):
                                    novas_msgs = pega_mensagens(atual)
                                    for novo_resultado in novas_msgs["result"]:
                                        atual = novo_resultado["update_id"] + 1
                                        nova_msg = novo_resultado.get("message")
                                        if not nova_msg:
                                            continue

                                        novo_texto = nova_msg.get("text", "").strip().lower()
                                        novo_cid = nova_msg["chat"]["id"]

                                        if novo_cid == cid and novo_texto in ["para", "parar", "stop"]:
                                            envia_telegram("⛔ Interrupção solicitada. Você pode iniciar novamente preenchendo o formulário.", cid)
                                            chats_respondidos.discard(cid)
                                            interrompe = True
                                            break
                                    if interrompe:
                                        break
                                    time.sleep(intervalo)
                            if interrompe:
                                break

                    else:
                        envia_telegram("⚠️ Formulário incompleto. Preencha todos os campos!", cid)
                except Exception as e:
                    print("Erro ao processar formulário:", e)
                    envia_telegram("⚠️ Erro ao processar a resposta. Verifique o formato e tente novamente.", cid)
            else:
                envia_telegram("❗Por favor, preencha o formulário exatamente como enviado, respondendo após os `:`.", cid)

        time.sleep(5)

@app.route("/")
def health_check():
    return "Aplicação em funcionamento!", 200

@app.route("/ping")
def alive():
    return "pong", 200


if __name__ == "__main__":
    print("Bot iniciado...")
    loop_telegram()
    print("⚠️ Resposta da API sem 'result':", response)
