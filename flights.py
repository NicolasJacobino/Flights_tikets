import http.client
import json
import urllib.parse
import time
import os
from datetime import datetime
from flask import Flask, request
from threading import Thread


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

'''def parse_custom_date(date_str):
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
    return datetime.strptime(full_date, "%d%m%Y").strftime("%Y-%m-%d")'''

def parse_custom_date(date_str):
    date_str = date_str.strip()
    formats = [
        "%d%m%y",     # 010124
        "%d%m%Y",     # 01012024
        "%d/%m/%Y",   # 01/01/2024
        "%d/%m/%y",   # 01/01/24
        "%d-%m-%Y",   # 01-01-2024
        "%d-%m-%y",   # 01-01-24
        "%Y%m%d",     # 20240101
    ]

    for fmt in formats:
        try:
            date = datetime.strptime(date_str, fmt)
            #return date.strftime("%d-%m-%y")  # <-- Aqui usamos %y para ano com 2 dígitos
            return date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return "erro: formato inválido"

def requisita_api(parametros_sem_horas):
    # parâmetros_sem_horas = 'ORIGEM;DESTINO;DATAPARTIDA;DATARETORNO;PRECOMIN;PRECOMAX'
    try:
        print(parametros_sem_horas)
        from_, to_, departure_date_raw, return_date_raw, price_min, price_max = parametros_sem_horas.split(';')
        print(from_)
        print(to_)
        print(price_min)
        print(price_max)
        departure_date = parse_custom_date(departure_date_raw)
        return_date = parse_custom_date(return_date_raw)
        price_min = float(price_min)
        price_max = float(price_max)
        print(departure_date)
        print(return_date)
        conn = http.client.HTTPSConnection("booking-com.p.rapidapi.com")
        headers = {
            'x-rapidapi-key': api_key,
            'x-rapidapi-host': "booking-com.p.rapidapi.com"
        }
        url = (
              f"/v1/flights/search?"
              f"from_code={from_}.AIRPORT&"
              f"depart_date={departure_date}&"
              f"page_number=0&"
              f"currency=BRL&"
              f"children_ages=0&"
              f"to_code={to_}.AIRPORT&"
              f"adults=1&"
              f"return_date={return_date}&"
              f"cabin_class=ECONOMY&"
              f"locale=pt-br&"
              f"flight_type=ROUNDTRIP&"
              f"order_by=CHEAPEST"
              )
        conn.request("GET", url, headers=headers)
        res = conn.getresponse()
        data = res.read().decode("utf-8")
        print(data)
        conn.close()

        api_dict = json.loads(data)
        flight_offers = api_dict.get('flightOffers', [])

        if not flight_offers:
            return "Erro: contate o servidor."

        offer = flight_offers[0]
        
        #Calculo de preços
        price_info = offer.get('priceBreakdown', {})
        price_total_info = price_info.get('total', {})
        price_base_info = price_info.get('baseFare', {})
        raw_carrier_ = price_info.get('carrierTaxBreakdown',[])
        carrier_ = raw_carrier_[0].get('carrier',{})
        ag_ = carrier_.get('name','???')
        
        #Calculo de conexoes
        raw_segments_ = offer.get('segments',[])
        
        #ida
        segments_ = raw_segments_[0]
        legs_ = segments_.get('legs',[])
        if len(legs_) == 1 :
            tempo_total_h_ = (segments_.get('totalTime',0)//3600)
            tempo_total_min_ = (segments_.get('totalTime',0)%3600)//60
            conexoes_ = f"O voo não possui conexões\n⏱️Tempo total da viagem estimado é {tempo_total_h_}H e {tempo_total_min_}min"
        elif len(legs_) == 2 :
            conexao1_ = legs_[1].get('departureAirport',{}).get('code','???')
            tempo_total_h_ = (segments_.get('totalTime',0)//3600)
            tempo_total_min_ = (segments_.get('totalTime',0)%3600)//60
            conexoes_ = f"✈️O voo de ida possui  1 conexão em {conexao1_} \n⏱️Tempo total da viagem estimado é {tempo_total_h_}H e {tempo_total_min_}min"
        elif len(legs_) == 3:
            conexao1_ = legs_[1].get('departureAirport',{}).get('code','???')
            conexao2_ = legs_[1].get('arrivalAirport',{}).get('code','???')
            tempo_total_h_ = (segments_.get('totalTime',0)//3600)
            tempo_total_min_ = (segments_.get('totalTime',0)%3600)//60
            conexoes_ = f"✈️O voo de ida possui  2 conexões em {conexao1_} e {conexao2_}\n⏱️Tempo total da viagem estimado é {tempo_total_h_}H e {tempo_total_min_}min"
        else:
            conexoes_ = "Não foi possível determinar as conexões do voo de ida."
        #volta
        if  len(raw_segments_) > 1 :
          segments1_ = raw_segments_[1]
          legs_ = segments1_.get('legs',[])
          if len(legs_) == 1 :
              tempo_total_h_v_ = (segments1_.get('totalTime',0)//3600)
              tempo_total_min_v_ = (segments1_.get('totalTime',0)%3600)//60
              conexoes_v_ = f"O voo não possui conexões\n⏱️Tempo total da viagem é {tempo_total_h_v_}H e {tempo_total_min_v_}min"
          elif len(legs_) == 2 :
              conexao1_v_ = legs_[1].get('departureAirport',{}).get('code','???')
              tempo_total_h_v_ = (segments1_.get('totalTime',0)//3600)
              tempo_total_min_v_ = (segments1_.get('totalTime',0)%3600)//60
              conexoes_v_ = f"✈️Voo de volta: 1 conexão em {conexao1_v_} \n⏱️Tempo total da viagem é {tempo_total_h_v_}H e {tempo_total_min_v_}min"
          elif len(legs_) >= 3:
              conexao1_v_ = legs_[1].get('departureAirport',{}).get('code','???')
              conexao2_v_ = legs_[1].get('arrivalAirport',{}).get('code','???')
              tempo_total_h_v_ = (segments1_.get('totalTime',0)//3600)
              tempo_total_min_v_ = (segments1_.get('totalTime',0)%3600)//60
              conexoes_v_ = f"✈️Voo de volta: 2 conexões em {conexao1_v_} e {conexao2_v_}\n⏱️Tempo total da viagem é {tempo_total_h_v_}H e {tempo_total_min_v_}min"
        else:
          conexoes_v_ = "Erro ao adquirir informações do voo de volta."
        #Calculo de bagagens
        
        price_total = price_total_info.get('units', 0) + price_total_info.get('nanos', 0) / 1e9
        price_base = price_base_info.get('units', 0) + price_base_info.get('nanos', 0) / 1e9

        if price_min < price_base < price_max:
            return f"💰 Oferta encontrada para o voo de {from_} a {to_}!\nPreço base (sem taxas): R$ {price_base:.2f}\nPreço total (com taxas): R$ {price_total:.2f}\n{conexoes_}\n{conexoes_v_}\nA Agência resposavel é {ag_}"
        else:
            return "Nenhum voo dentro da faixa de preço informada."

    except Exception as e:
        return f"Erro ao consultar API: {e}"

def atende_usuario(cid, texto_formulario, atual_inicial, chats_respondidos, usuarios_em_execucao):
    try:
        linhas = texto_formulario.split('\n')
        valores = [linha.split(':', 1)[1].strip().upper() for linha in linhas if ':' in linha]
       #-------------------------------------------------------------------# 
        #Tratamento de Erros digitados pelo user na hora do preenchimento
        if len(valores) != 7:
            envia_telegram("⚠️ Formulário incompleto. Preencha todos os campos!", cid)
            usuarios_em_execucao.discard(cid)
            return
        if len(valores[0])>3 or len(valores[1])>3:
            envia_telegram("Erro: Coloque apenas o código do aeroporto.Preencha corretamente o formulário",cid)
            usuarios_em_execucao.discard(cid)
            return 
        today = datetime.today().date()
        departure_date_obj = datetime.strptime(parse_custom_date(valores[2]), "%Y-%m-%d")
        return_date_obj = datetime.strptime(parse_custom_date(valores[3]), "%Y-%m-%d")
        if departure_date_obj.date() < today:
            envia_telegram("Erro: A data de partida não pode ser anterior a hoje.Preencha corretamente o formulário",cid)
            usuarios_em_execucao.discard(cid)
            return 
        if return_date_obj.date() < today:
            envia_telegram("Erro: A data de retorno não pode ser anterior a hoje.",cid)
            usuarios_em_execucao.discard(cid)
            return 
        if return_date_obj < departure_date_obj:
            envia_telegram("Erro: A data de retorno não pode ser anterior à data de partida.",cid)
            usuarios_em_execucao.discard(cid)
            return 
        if valores[4] > valores[5]:
            envia_telegram("Erro: O valor mínimo não pode ser maior que o máximo.",cid)
            usuarios_em_execucao.discard(cid)
            return 
        #-------------------------------------------------------------------#
        parametros_str = ';'.join(valores[:6])
        print(parametros_str)
        horas_reais = int(valores[6])
        print(horas_reais)
        raw_horas = (int(valores[6])*3600)//4
        print(raw_horas)
        if raw_horas//3600 <1:
            horas = 1
        else:
          horas =  raw_horas//3600
        print(raw_horas)
        envia_telegram(f"Buscando voos por {horas_reais} hora(s)...\nPara cancelar digite 'parar'", cid)

        interrompe = False
        atual = atual_inicial

        for h in range(horas):
            #envia_telegram(f"🔎 Verificação {h+1}/{horas} em andamento...", cid)
            resposta = requisita_api(parametros_str)
            if resposta != 'Nenhum voo dentro da faixa de preço informada.':
                envia_telegram(resposta, cid)
            print(resposta)

            if h < horas - 1:
                tempo_total = 2500*4  # duração do intervalo em segundos
                intervalo = 5       # intervalo para checar mensagens
                ciclos = tempo_total // intervalo

                for _ in range(ciclos):
                    interrompe = False
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
                            #break
                            return
                    if interrompe:
                        break
                    time.sleep(intervalo)
            if interrompe:
                break
    except Exception as e:
        print("Erro ao processar formulário:", e)
        envia_telegram("⚠️ Erro ao processar a resposta. Verifique o formato e tente novamente.", cid)
    finally:
        if cid in chats_respondidos:
          chats_respondidos.discard(cid)
        usuarios_em_execucao.discard(cid)
        envia_telegram("Fim da pesquisa!\nPara reiniciar preencha novamente o formulário", cid)
        envia_telegram (
                    "Local de partida: \n"
                    "Local de chegada: \n"
                    "Data de partida: \n"
                    "Data de retorno: \n"
                    "Valor mínimo da passagem: \n"
                    "Valor máximo da passagem: \n"
                    "Horas de execução do serviço:"
                ,cid)

def loop_telegram():
    atual = 0
    chats_respondidos = set()
    usuarios_em_execucao = set()

    while True:
        updates = pega_mensagens(atual)
        for resultado in updates.get("result", []):
            atual = resultado["update_id"] + 1
            mensagem = resultado.get("message")
            if not mensagem:
                continue

            text = mensagem.get("text", "")
            print(text)
            cid = mensagem["chat"]["id"]
            first_name = mensagem["chat"].get("first_name", "usuário")

            # PRIMEIRA INTERAÇÃO
            if cid not in chats_respondidos and cid not in usuarios_em_execucao:
                mensagem1 = (
                    f"Olá {first_name} ✈️\nPor favor, preencha o formulário abaixo. "
                    f"Para pesquisa utilize apenas o código do aeroporto, ex: CNF."
                )
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

            # PROCESSA FORMULÁRIO
            campos_necessarios = [
                "local de partida:", "local de chegada:", "data de partida:",
                "data de retorno:", "valor mínimo da passagem:",
                "valor máximo da passagem:", "horas de execução do serviço:"
            ]

            texto_recebido = text.lower()

            campos_presentes = [campo for campo in campos_necessarios if campo in texto_recebido]
            formulario_completo = len(campos_presentes) == len(campos_necessarios)

            if cid not in usuarios_em_execucao:
                if formulario_completo:
                    print('✅ Formulário completo. Iniciando atendimento...')
                    usuarios_em_execucao.add(cid)
                    print(usuarios_em_execucao)
                    Thread(target=atende_usuario, args=(cid, text, atual, chats_respondidos, usuarios_em_execucao)).start()
                else:
                    campos_faltando = [campo for campo in campos_necessarios if campo not in texto_recebido]
                    print('❌ Formulário incompleto. Faltam:', campos_faltando)

                    mensagem_erro = (
                        "❌ O formulário está incompleto. Faltam os seguintes campos:\n"
                        + "\n".join(f"- {campo}" for campo in campos_faltando) +
                        "\n\nPor favor, preencha novamente usando o formato correto:"
                    )
                    envia_telegram(mensagem_erro, cid)

                    exemplo = (
                        "Local de partida: CNF\n"
                        "Local de chegada: VIX\n"
                        "Data de Partida: 2025-06-01\n"
                        "Data de retorno: 2025-07-01\n"
                        "Valor mínimo da passagem: 100\n"
                        "Valor máximo da passagem: 1500\n"
                        "Horas de execução do serviço: 200"
                    )
                    envia_telegram(exemplo, cid)

        time.sleep(5)
@app.route("/")
def health_check():
    return "Aplicação em funcionamento!", 200

@app.route("/ping")
def alive():
    return "pong", 200


def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    loop_telegram()  # sua função principal que roda o bot
