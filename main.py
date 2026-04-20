import asyncio
import logging
import os
import re
import json
import httpx
import random
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# --- SERVIDOR WEB DE MENTIRA ---
app_web = Flask("")

@app_web.route('/')
def home():
    return "Bot do NBA Tracker está online e operando!"

def rodar_site_falso():
    porta = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=porta)

def manter_vivo():
    t = Thread(target=rodar_site_falso)
    t.start()
# --------------------------------

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("NBA_Tracker")

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

CONTAS_ESPECIFICAS = ["WizBetz", "Gambler77Goated", "LuffyBetss", "ThePropAnt", "772_Bets", "KCLuke", "UnderdogSA1"]
tweets_processados = set()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
]

def validar_tweet(texto):
    if not texto: return False
    texto_limpo = texto.lower()
    
    palavras_proibidas = ['recap', 'cash', 'green', 'deposit', 'sign up', 'bonus', 'vip', 'giveaway']
    emojis_resultado = ['✅', '❌', '💰']
    
    if any(p in texto_limpo for p in palavras_proibidas) or any(e in texto for e in emojis_resultado):
        return False

    filtro_esportes = r'(nba|playoff|nfl|mlb|basketball)'
    filtro_stats = r'(over|under|o\d|u\d|pra|pts|points|reb|rebounds|ast|assists|3pm|3pa|ra|pr|pa|reb\+ast|pts\+reb|pts\+ast)'
    
    tem_esporte = bool(re.search(filtro_esportes, texto_limpo))
    tem_stat = bool(re.search(filtro_stats, texto_limpo))
    
    if not (tem_esporte and tem_stat):
        logger.info(f"🔍 Descartado (Não bateu estatística): {texto[:40]}...")
        
    return tem_esporte and tem_stat

def extrair_apenas_aposta(texto):
    linhas = texto.split('\n')
    aposta_isolada = []
    termos_chave = r'(over|under|o\d|u\d|pra|pts|points|reb|ast|3pm|ra|pr|pa|\+)'
    
    for linha in linhas:
        if re.search(r'\d', linha) and re.search(termos_chave, linha.lower()) and "http" not in linha.lower():
            aposta_isolada.append(linha.strip())
            
    return "\n".join(aposta_isolada) if aposta_isolada else texto.strip()

async def enviar_telegram(texto_bruto, data_tweet):
    data_brasil = data_tweet - timedelta(hours=3)
    data_formatada = data_brasil.strftime("%d/%m/%Y")
    hora_formatada = data_brasil.strftime("%H:%M")
    texto_limpo = extrair_apenas_aposta(texto_bruto)
    
    msg = (f"🚨 **ALERTA DE APOSTA** 🚨\n\n"
           f"🗓️ **Data:** {data_formatada}\n"
           f"⏰ **Hora:** {hora_formatada}\n"
           f"➖➖➖➖➖➖➖➖➖➖\n"
           f"📝 _{texto_limpo}_\n"
           f"➖➖➖➖➖➖➖➖➖➖")
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True}
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, data=payload)
            logger.info("✅ Nova pick enviada!")
        except Exception as e:
            logger.error(f"❌ Erro ao enviar Telegram: {e}")

async def ler_tweets_ocultos(username):
    quebrador = random.randint(100000, 999999)
    url_alvo = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}?_={quebrador}"
    url_codificada = urllib.parse.quote(url_alvo, safe='')
    
    # Rotação Estratégica: Tenta direto primeiro, depois proxies alternativos
    tuneis = [
        url_alvo, 
        f"https://api.allorigins.win/get?url={url_codificada}",
        f"https://api.codetabs.com/v1/proxy?quest={url_codificada}"
    ]
    
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    html_pagina = ""
    
    async with httpx.AsyncClient() as client:
        for tunel in tuneis:
            try:
                resposta = await client.get(tunel, headers=headers, timeout=15.0)
                if resposta.status_code == 200:
                    if "allorigins" in tunel:
                        html_pagina = resposta.json().get("contents", "")
                    else:
                        html_pagina = resposta.text
                    if html_pagina: break 
            except Exception:
                continue 
                
    if not html_pagina:
        logger.warning(f"⚠️ Todos os métodos falharam para @{username}.")
        return []
            
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html_pagina)
    if not match: return []
        
    try:
        dados = json.loads(match.group(1))
        instrucoes = dados.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])
        
        encontrados = []
        for item in instrucoes[:10]:
            if item.get("type") == "tweet":
                tweet = item.get("content", {}).get("tweet", {})
                texto = tweet.get("full_text", "")
                id_str = tweet.get("id_str", "")
                data_str = tweet.get("created_at", "") 
                
                if texto and id_str and data_str:
                    data_tweet = datetime.strptime(data_str, '%a %b %d %H:%M:%S +0000 %Y')
                    agora = datetime.utcnow()
                    # Mantendo 48h para garantir que você receba algo no teste
                    if (agora - data_tweet).total_seconds() / 3600 > 48: continue 
                    encontrados.append({"id": id_str, "text": texto, "data": data_tweet})
        return encontrados
    except Exception:
        return []

async def loop_principal():
    logger.info("Bot Iniciado com sucesso! Limpeza de cache concluída.")
    while True:
        for conta in CONTAS_ESPECIFICAS:
            try:
                tweets = await ler_tweets_ocultos(conta)
                for t in tweets:
                    id_t = t["id"]
                    if id_t not in tweets_processados:
                        if validar_tweet(t["text"]):
                            await enviar_telegram(t["text"], t["data"])
                        tweets_processados.add(id_t)
                await asyncio.sleep(random.randint(5, 10))
            except Exception: pass
        await asyncio.sleep(180)

if __name__ == "__main__":
    manter_vivo()
    try: asyncio.run(loop_principal())
    except KeyboardInterrupt: pass