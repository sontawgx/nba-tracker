import asyncio
import logging
import os
import re
import json
import httpx
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- O DISFARCE (SERVIDOR WEB DE MENTIRA) ---
from flask import Flask
from threading import Thread

app_web = Flask("")

@app_web.route('/')
def home():
    return "Bot do NBA Tracker está online e vigiando!"

def rodar_site_falso():
    # O Render exige que o site rode na porta que ele define ou na 10000
    porta = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=porta)

def manter_vivo():
    t = Thread(target=rodar_site_falso)
    t.start()
# ---------------------------------------------

# 1. CONFIGURAÇÕES INICIAIS
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger("NBA_Tracker")

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    logger.error("🚨 ERRO CRÍTICO: As chaves do Telegram não foram encontradas no .env.")
    exit()

tweets_processados = set()

CONTAS_ESPECIFICAS = ["WizBetz", "Gambler77Goated", "LuffyBetss", "ThePropAnt", "772_Bets", "KCLuke", "UnderdogSA1"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
]

# 2. A "PENEIRA" (Validação e Extração)
def validar_tweet(texto):
    if not texto: return False
    texto_limpo = texto.lower()
    
    palavras_proibidas = ['recap', 'cash', 'green'] 
    emojis_resultado = ['✅', '❌']
    
    if any(palavra in texto_limpo for palavra in palavras_proibidas) or any(emoji in texto for emoji in emojis_resultado):
        return False

    filtro_esportes = r'\b(nba|nfl|mlb)\b'
    filtro_stats = r'\b(o|u|over|under|pra|pts|3pm|3pa|fga|fgm|ra|pr|p\+r|pa)\b'
    
    tem_esporte = bool(re.search(filtro_esportes, texto_limpo))
    tem_stat = bool(re.search(filtro_stats, texto_limpo))
    
    return tem_esporte and tem_stat

def extrair_apenas_aposta(texto):
    linhas = texto.split('\n')
    aposta_isolada = []
    filtro_stats = r'\b(o|u|over|under|pra|pts|3pm|3pa|fga|fgm|ra|pr|p\+r|pa)\b'
    
    for linha in linhas:
        linha_limpa = linha.lower()
        if re.search(filtro_stats, linha_limpa) and re.search(r'\d', linha_limpa):
            aposta_isolada.append(linha.strip())
            
    if aposta_isolada: return "\n".join(aposta_isolada)
    return texto.strip()

# 3. MENSAGEM DO TELEGRAM
async def enviar_telegram(texto_bruto, data_tweet):
    data_brasil = data_tweet - timedelta(hours=3)
    data_formatada = data_brasil.strftime("%d/%m/%Y")
    hora_formatada = data_brasil.strftime("%H:%M")
    
    texto_limpo = extrair_apenas_aposta(texto_bruto)
    
    msg = (
        f"🚨 **ALERTA DE APOSTA** 🚨\n\n"
        f"🗓️ **Data:** {data_formatada}\n"
        f"⏰ **Hora:** {hora_formatada}\n"
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"📝 _{texto_limpo}_\n"
        f"➖➖➖➖➖➖➖➖➖➖"
    )
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True}
    
    async with httpx.AsyncClient() as client:
        try:
            resposta = await client.post(url, data=payload)
            resposta.raise_for_status()
            logger.info("✅ Nova pick enviada!")
        except Exception as e:
            logger.error(f"❌ Erro ao enviar para Telegram: {e}")

# 4. A TUBULAÇÃO DE LEITURA 
async def ler_tweets_ocultos(username):
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    try:
        async with httpx.AsyncClient() as client:
            resposta = await client.get(url, headers=headers)
            if resposta.status_code == 429: return []
                
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', resposta.text)
        if not match: return []
            
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
                    try:
                        data_tweet = datetime.strptime(data_str, '%a %b %d %H:%M:%S +0000 %Y')
                        agora = datetime.utcnow()
                        if (agora - data_tweet).total_seconds() / 3600 > 24: continue 
                    except Exception as e: continue 
                        
                    encontrados.append({"id": id_str, "text": texto, "data": data_tweet})
                    
        return encontrados
    except Exception as e: return []

# 5. MOTOR PRINCIPAL
async def loop_principal():
    logger.info("Bot Iniciado! Filtro de Horas, Extração e Disfarce Web ativados.")
    while True:
        for conta in CONTAS_ESPECIFICAS:
            try:
                tweets_recentes = await ler_tweets_ocultos(conta)
                for t in tweets_recentes:
                    id_tweet = t["id"]
                    if id_tweet not in tweets_processados:
                        if validar_tweet(t["text"]):
                            await enviar_telegram(t["text"], t["data"])
                        tweets_processados.add(id_tweet)
                await asyncio.sleep(random.randint(5, 10))
            except Exception as e: pass
        await asyncio.sleep(180)

if __name__ == "__main__":
    manter_vivo() # Liga o site de mentira
    try: asyncio.run(loop_principal()) # Liga o robô
    except KeyboardInterrupt: pass