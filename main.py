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

# --- O DISFARCE (SERVIDOR WEB DE MENTIRA) ---
from flask import Flask
from threading import Thread

app_web = Flask("")

@app_web.route('/')
def home():
    return "Bot do NBA Tracker está online e vigiando através do Túnel CodeTabs!"

def rodar_site_falso():
    porta = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=porta)

def manter_vivo():
    t = Thread(target=rodar_site_falso)
    t.start()
# ---------------------------------------------

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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
]

def validar_tweet(texto):
    if not texto: return False
    texto_limpo = texto.lower()
    
    # === LISTA NEGRA BLINDADA ===
    # Bloqueia Emojis de Resultados/Vendas e palavras de link de afiliado
    emojis_resultado = ['✅', '❌', '💰', '🔥', '👇']
    palavras_proibidas = ['recap', 'cash', 'green', 'deposit', 'sign up', 'code', 'bonus', 'free picks', 'vip', 'link', 'match up to']
    
    if any(palavra in texto_limpo for palavra in palavras_proibidas) or any(emoji in texto for emoji in emojis_resultado):
        return False

    # === LISTA BRANCA ESTRITA (\b garante que é a palavra exata) ===
    filtro_esportes = r'\b(nba|nfl|mlb|basketball)\b'
    # Pega stats exatas OU letras O/U coladas em números (ex: o22.5)
    filtro_stats = r'\b(over|under|pra|pts|points|reb|rebounds|ast|assists|3pm|3pa|fga|fgm|ra|pr|p\+r|pa)\b|\bo\d|\bu\d'
    
    tem_esporte = bool(re.search(filtro_esportes, texto_limpo))
    tem_stat = bool(re.search(filtro_stats, texto_limpo))
    
    return tem_esporte and tem_stat

def extrair_apenas_aposta(texto):
    linhas = texto.split('\n')
    if len(linhas) <= 2: return texto.strip()
        
    aposta_isolada = []
    filtro_stats = r'\b(over|under|pra|pts|points|reb|rebounds|ast|assists|3pm|3pa|fga|fgm|ra|pr|p\+r|pa)\b|\bo\d|\bu\d'
    
    for linha in linhas:
        # Pega a linha só se tiver a estatística, um número e não for um link HTTP
        if re.search(filtro_stats, linha.lower()) and re.search(r'\d', linha) and "http" not in linha.lower():
            aposta_isolada.append(linha.strip())
            
    return "\n".join(aposta_isolada) if aposta_isolada else texto.strip()

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

# --- A TUBULAÇÃO ATUALIZADA (NOVO TÚNEL CODETABS) ---
async def ler_tweets_ocultos(username):
    quebrador = random.randint(10000, 99999)
    url_alvo = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}?_={quebrador}"
    
    url_codificada = urllib.parse.quote(url_alvo, safe='')
    # Novo Proxy mais estável
    url_proxy = f"https://api.codetabs.com/v1/proxy?quest={url_codificada}"
    
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    try:
        async with httpx.AsyncClient() as client:
            resposta = await client.get(url_proxy, headers=headers, timeout=20.0)
            
            # Se der erro 500 ou 429, apenas avisa e segue a vida sem travar
            if resposta.status_code != 200: 
                logger.warning(f"⚠️ Proxy falhou (Status {resposta.status_code}) ao ler @{username}. Tentaremos no próximo ciclo.")
                return []
                
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
    except Exception as e: 
        logger.debug(f"Erro menor no túnel @{username}: {e}")
        return []

async def loop_principal():
    logger.info("Bot Iniciado! Túnel CodeTabs e Lista Negra Restrita ativados.")
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
    manter_vivo()
    try: asyncio.run(loop_principal())
    except KeyboardInterrupt: pass