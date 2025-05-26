import os
import json
import http.client
from datetime import datetime
from flask import Flask, request
from flight_search import buscar_voos  # exemplo: importe corretamente sua função

app = Flask(__name__)

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

def buscar_voos(parametros_str):
    try:
        partes = parametros_str.strip().split(";")
        if len(partes) != 6:
            return "Erro: são esperados 6 parâmetros separados por ponto e vírgula."

        origem, destino, data_ida, data_volta, preco_min, preco_max = partes

        data_ida = parse_custom_date(data_ida)
        data_volta = parse_custom_date(data_volta)
        preco_min = float(preco_min)
        preco_max = float(preco_max)

        conn = http.client.HTTPSConnection("booking-com.p.rapidapi.com")

        headers = {
            'x-rapidapi-key': os.environ["API_KEY"],
            'x-rapidapi-host': "booking-com.p.rapidapi.com"
        }

        url = (
            f"/v1/flights/search?from_code={origem}.AIRPORT"
            f"&to_code={destino}.AIRPORT"
            f"&depart_date={data_ida}"
            f"&return_date={data_volta}"
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

        api_dict = json.loads(data.decode("utf-8"))
        flight_offers = api_dict.get('flightOffers', [])

        if not flight_offers:
            return "Nenhuma oferta de voo encontrada."

        offer = flight_offers[0]
        price_info = offer.get('priceBreakdown', {})
        price_total_info = price_info.get('total', {})
        price_base_info = price_info.get('baseFare', {})

        price_total = price_total_info.get('units', 0) + price_total_info.get('nanos', 0) / 1e9
        price_base = price_base_info.get('units', 0) + price_base_info.get('nanos', 0) / 1e9

        if preco_min < price_base < preco_max:
            return f"🛫 Voo de {origem} para {destino}\n💵 Base: R$ {price_base:.2f}\n💰 Total: R$ {price_total:.2f}"
        else:
            return "Nenhum voo dentro da faixa de preço informada."

    except Exception as e:
        return f"Erro ao buscar voo: {e}"

app = Flask(__name__)

@app.route("/")
def health_check():
    return "Aplicação em funcionamento!", 200

@app.route("/voos", methods=["GET"])
def rota_voos():
    mensagem = request.args.get("mensagem", "")
    return buscar_voos(mensagem)
