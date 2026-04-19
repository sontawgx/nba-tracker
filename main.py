def validar_tweet(texto):
    if not texto: return False
    texto_limpo = texto.lower()
    
    # Removemos o bloqueio de emojis ✅ e ❌ para não perder picks que citam ontem
    # Deixamos apenas a palavra 'recap' como bloqueio real
    if 'recap' in texto_limpo:
        return False

    # Lista Branca: Agora aceita O ou U mesmo que esteja colado no número
    filtro_esportes = r'(nba|nfl|mlb)'
    filtro_stats = r'(o\d|u\d|\bo\b|\bu\b|over|under|pra|pts|3pm|3pa|fga|fgm|ra|pr|p\+r|pa)'
    
    tem_esporte = bool(re.search(filtro_esportes, texto_limpo))
    tem_stat = bool(re.search(filtro_stats, texto_limpo))
    
    # Log de depuração (aparece no Render)
    if not (tem_esporte and tem_stat):
        logger.info(f"Tweet ignorado por falta de palavras-chave: {texto[:30]}...")
        
    return tem_esporte and tem_stat

def extrair_apenas_aposta(texto):
    linhas = texto.split('\n')
    # Se o tweet tiver poucas linhas, manda ele inteiro para garantir
    if len(linhas) <= 2:
        return texto.strip()
        
    aposta_isolada = []
    # Filtro mais aberto para capturar a linha da aposta
    filtro_stats = r'(o|u|over|under|pra|pts|3pm|3pa|fga|fgm|ra|pr|p\+r|pa)'
    
    for linha in linhas:
        if re.search(filtro_stats, linha.lower()) and re.search(r'\d', linha):
            aposta_isolada.append(linha.strip())
            
    return "\n".join(aposta_isolada) if aposta_isolada else texto.strip()