import http.client
import json
import urllib.parse
from datetime import datetime, timedelta
import time
import os


def parse_custom_date(date_str):
    if len(date_str) == 6:
        day = date_str[:2]
        month = date_str[2:4]
        year = '20' + date_str[4:]
        full_date = f"{day}{month}{year}"
    elif len(date_str) == 8:
        full_date = date_str
    else:
        raise ValueError("Formato inválido. Use ddmmaa ou ddmmaaaa.")
    return datetime.strptime(full_date, "%d%m%Y").strftime("%Y-%m-%d")


def get_updates(token, offset=None):
    conn = http.client.HTTPSConnection("api.telegram.org")
    params = f"?offset={offset}" if offset else ""
    endpoint = f"/bot{token}/getUpdates{params}"

    conn.request("GET", endpoint)
    res = conn.getresponse()
    data = res.read().decode("utf-8")
    conn.close()

    try:
        updates = json.loads(data)
        if "result" in updates and updates["result"]:
            last_update = updates["result"][-1]
            chat_id = last_update.get("message", {}).get("chat", {}).get("id")
            first_name = last_update.get("message", {}).get("from", {}).get("first_name")
            text_chat = last_update.get("message", {}).get("text")
            update_id = last_update.get("update_id")
            return chat_id, first_name, text_chat, update_id
        else:
            return None, None, None, None
    except Exception as e:
        print(f"Erro ao processar a resposta: {e}")
        return None, None, None, None


def send_message_to_telegram(chat_id, text, token):
    conn = http.client.HTTPSConnection("api.telegram.org")
    text_encoded = urllib.parse.quote_plus(text)
    endpoint = f"/bot{token}/sendMessage?chat_id={chat_id}&text={text_encoded}&parse_mode=Markdown"

    conn.request("GET", endpoint)
    res = conn.getresponse()
    res.read()  # Ler para liberar conexão
    conn.close()
    print("Mensagem enviada ao Telegram.")



def buscar_voos(from_, to_, departure_date, return_date, price_min, price_max):
    conn = http.client.HTTPSConnection("booking-com.p.rapidapi.com")

    headers = {
        'x-rapidapi-key': "293ce6e8femshc37232362435587p11a4e9jsn099831f6d5c6",
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
    data = res.read()
    conn.close()

    api_raw = data.decode("utf-8")

    try:
        api_dict = json.loads(api_raw)
        print(api_dict)
        flight_offers = api_dict.get('flightOffers', [])
        print(flight_offers)
        if not flight_offers:
            return "Nenhuma oferta de voo encontrada."

        offer = flight_offers[0]
        price_info = offer.get('priceBreakdown', {})
        price_total_info = price_info.get('total', {})
        price_base_info = price_info.get('baseFare', {})

        price_total = price_total_info.get('units', 0) + price_total_info.get('nanos', 0) / 1e9
        price_base = price_base_info.get('units', 0) + price_base_info.get('nanos', 0) / 1e9

        if price_min < price_base < price_max:
            return f"Preço total sem taxas: {price_base:.2f}\nPreço total com taxas: {price_total:.2f}"
        else:
            return "Nenhum voo dentro da faixa de preço informada."

    except Exception as e:
        return f"Erro ao processar resposta da API: {e}"


# --- Main loop ---

token = os.getenv("TELEGRAM_TOKEN")

if not token:
    raise ValueError("Variável TELEGRAM_TOKEN não configurada.")
offset = None

primeira_vez = True  # 👈 Flag para primeira mensagem depois de rodar o script

print("Bot iniciado e aguardando mensagens...")

while True:
    chat_id, first_name, texto, update_id = get_updates(token, offset)

    if chat_id and texto:
        if primeira_vez:
            mensagem_boas_vindas = (
                f"Olá {first_name} ✈️\n"
                "Para onde você quer voar?\n\n"
                "Descreva sua busca no seguinte formato:\n"
                "`ORIGEM;DESTINO;DATAPARTIDA;DATARETORNO;PRECOMIN;PRECOMAX;TEMPO_HORAS`\n\n"
                "*Exemplo:* `CNF;GRU;120525;250525;300;800;5`"
            )
            send_message_to_telegram(chat_id, mensagem_boas_vindas, token)
            primeira_vez = False  # 👈 A partir daqui, desativa
            offset = update_id + 1
            continue

        try:
            parts = texto.strip().split(';')
            if len(parts) == 7:
                from_ = parts[0].strip().upper()
                to_ = parts[1].strip().upper()
                departure_date = parse_custom_date(parts[2].strip())
                return_date = parse_custom_date(parts[3].strip())
                price_min = int(parts[4].strip())
                price_max = int(parts[5].strip())
                horas = float(parts[6].strip())

                send_message_to_telegram(chat_id, f"Buscando voos por {horas} horas. Vou avisar se encontrar algo dentro do preço.", token)

                fim = datetime.now() + timedelta(hours=horas)
                intervalo_segundos = 3600

                while datetime.now() < fim:
                    resposta = buscar_voos(from_, to_, departure_date, return_date, price_min, price_max)
                    print(resposta)
                    if "Nenhum voo dentro da faixa" not in resposta and "Nenhuma oferta" not in resposta and "Erro" not in resposta:
                        send_message_to_telegram(chat_id, f"Oferta encontrada:\n{resposta}", token)
                    else:
                        print(f"{datetime.now()}: Nenhuma oferta válida encontrada.")

                    time.sleep(intervalo_segundos)

                send_message_to_telegram(chat_id, f"Monitoramento encerrado após {horas} horas.", token)

            else:
                mensagem_erro = (
                    "Formato incorreto. Envie:\n"
                    "`ORIGEM;DESTINO;DATAPARTIDA;DATARETORNO;PRECOMIN;PRECOMAX;TEMPO_HORAS`\n"
                    "*Exemplo:* `CNF;GRU;120525;250525;300;800;5`"
                )
                send_message_to_telegram(chat_id, mensagem_erro, token)

        except Exception as e:
            send_message_to_telegram(chat_id, f"Erro ao processar sua mensagem: {e}", token)

        offset = update_id + 1

    else:
        time.sleep(2)

