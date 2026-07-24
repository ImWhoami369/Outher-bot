import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import ccxt
import pandas as pd
import requests
import telebot
from telebot import types

# ======================================================
# 1. CONFIGURAÇÕES E CHAVES
# ======================================================
TOKEN = '8633142310:AAEzfPzJQiUx9TzTOGIQMkrI0yC3SN5lIxM'
CHAT_ID = '-1003981624573'
RENDER_URL = "https://bottelegram-1-jtr3.onrender.com"  # Substitua pela sua URL do Render quando subir

bot = telebot.TeleBot(TOKEN)
bot_rodando = True  # Flag global para Pausar/Iniciar varredura

SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'DOGE/USDT', 'XRP/USDT',
    'ADA/USDT', 'AVAX/USDT', 'LINK/USDT', 'NEAR/USDT', '1000PEPE/USDT',
    '1000SHIB/USDT', 'SUI/USDT', 'BNB/USDT', 'OP/USDT', 'ARB/USDT'
]

TIMEFRAME = '1m'
TS_PCT = 1.0  # Trailing Stop de 1.0%

exchange = ccxt.binanceusdm({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

posicoes = {
    symbol: {'ativa': False, 'tipo': None, 'entrada': 0.0, 'ts_price': 0.0}
    for symbol in SYMBOLS
}

# ======================================================
# 2. PAINEL INTERATIVO E BOTÕES DO TELEGRAM
# ======================================================

# Menu Fixo de Comandos
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_status = types.KeyboardButton('📊 Status')
    btn_posicoes = types.KeyboardButton('📂 Posições Abertas')
    btn_pausar = types.KeyboardButton('⏸️ Pausar Bot')
    btn_iniciar = types.KeyboardButton('▶️ Iniciar Bot')
    
    markup.add(btn_status, btn_posicoes, btn_pausar, btn_iniciar)
    bot.send_message(
        message.chat.id, 
        "🤖 <b>PAINEL DE CONTROLE M1 ULTRA SCALPER</b>\n\nEscolha uma opção no teclado abaixo:", 
        parse_mode="HTML", 
        reply_markup=markup
    )

@bot.message_handler(func=lambda msg: msg.text == '📊 Status' or msg.text == '/status')
def cmd_status(message):
    estado = "🟢 <b>ANALISANDO</b>" if bot_rodando else "🔴 <b>PAUSADO</b>"
    ativas = sum(1 for p in posicoes.values() if p['ativa'])
    
    texto = (
        f"📊 <b>STATUS DO SISTEMA</b>\n\n"
        f"• Estado do Bot: {estado}\n"
        f"• Pares Monitorados: {len(SYMBOLS)}\n"
        f"• Operações Ativas: {ativas}\n"
        f"• Trailing Stop: {TS_PCT}%\n"
    )
    bot.reply_to(message, texto, parse_mode="HTML")

@bot.message_handler(func=lambda msg: msg.text == '📂 Posições Abertas' or msg.text == '/posicoes')
def cmd_posicoes(message):
    texto = "📂 <b>POSIÇÕES ATIVAS NO MOMENTO:</b>\n\n"
    encontrou = False
    
    for symbol, pos in posicoes.items():
        if pos['ativa']:
            encontrou = True
            clean_sym = symbol.replace('/', '').replace(':USDT', '')
            texto += f"• <b>#{clean_sym}</b> | {pos['tipo']} | Entrada: ${pos['entrada']:.6f} | Stop: ${pos['ts_price']:.6f}\n"
            
    if not encontrou:
        texto += "<i>Nenhuma posição aberta no momento.</i>"
        
    bot.reply_to(message, texto, parse_mode="HTML")

@bot.message_handler(func=lambda msg: msg.text == '⏸️ Pausar Bot' or msg.text == '/pausar')
def cmd_pausar(message):
    global bot_rodando
    bot_rodando = False
    bot.reply_to(message, "⏸️ <b>Varredura de sinais PAUSADA!</b>\nAs posições abertas continuam sendo monitoradas.", parse_mode="HTML")

@bot.message_handler(func=lambda msg: msg.text == '▶️ Iniciar Bot' or msg.text == '/iniciar')
def cmd_iniciar(message):
    global bot_rodando
    bot_rodando = True
    bot.reply_to(message, "▶️ <b>Varredura REINICIADA!</b> Buscando novos cruzamentos em M1...", parse_mode="HTML")

# Gerenciador do Botão Inline de "Fechar Posição"
@bot.callback_query_handler(func=lambda call: call.data.startswith('close_'))
def callback_close_position(call):
    symbol_code = call.data.replace('close_', '')
    target_symbol = None
    
    for sym in SYMBOLS:
        if sym.replace('/', '').replace(':USDT', '') == symbol_code:
            target_symbol = sym
            break
            
    if target_symbol and posicoes[target_symbol]['ativa']:
        posicoes[target_symbol]['ativa'] = False
        bot.answer_callback_query(call.id, text=f"Posição {symbol_code} encerrada manualmente!")
        bot.send_message(CHAT_ID, f"🛑 <b>OPERAÇÃO ENCERRADA MANUALLY</b> em #{symbol_code} via painel do Telegram.", parse_mode="HTML")
    else:
        bot.answer_callback_query(call.id, text="Essa posição já não está mais ativa.")

def escutar_telegram():
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

threading.Thread(target=escutar_telegram, daemon=True).start()

# ======================================================
# 3. DUMMY SERVER & AUTO-PING PARA O RENDER
# ======================================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Scalper M1 Interativo Ativo!")
    def log_message(self, format, *args): return

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()

def keep_alive():
    while True:
        try:
            time.sleep(600)
            if "seu-bot" not in RENDER_URL:
                requests.get(RENDER_URL, timeout=10)
        except Exception as e:
            print(f"Erro auto-ping: {e}")

threading.Thread(target=keep_alive, daemon=True).start()

# ======================================================
# 4. AUXILIARES E LÓGICA DE MERCADO
# ======================================================
def enviar_telegram_com_botao(mensagem, symbol_code):
    markup = types.InlineKeyboardMarkup()
    btn_fechar = types.InlineKeyboardButton("❌ Fechar Posição", callback_data=f"close_{symbol_code}")
    markup.add(btn_fechar)
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": markup.to_json()
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

def enviar_telegram_simples(mensagem):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": mensagem,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

def calcular_indicadores(df):
    df['ema_fast'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=21, adjust=False).mean()
    
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    ema_gain = gain.ewm(com=13, adjust=False).mean()
    ema_loss = loss.ewm(com=13, adjust=False).mean()
    rs = ema_gain / ema_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

def analisar_e_executar():
    for symbol in SYMBOLS:
        try:
            bars = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=60)
            df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = calcular_indicadores(df)

            ultima_fechada = df.iloc[-2]
            penultima = df.iloc[-3]
            preco_atual = df.iloc[-1]['close']
            high_atual = df.iloc[-1]['high']
            low_atual = df.iloc[-1]['low']

            pos = posicoes[symbol]
            hashtag = symbol.replace('/', '').replace(':USDT', '')

            # GERENCIAMENTO DE POSIÇÃO (TRAILING STOP)
            if pos['ativa']:
                if pos['tipo'] == 'BUY':
                    novo_ts = high_atual * (1 - (TS_PCT / 100))
                    pos['ts_price'] = max(pos['ts_price'], novo_ts)

                    if low_atual <= pos['ts_price']:
                        pnl = ((pos['ts_price'] - pos['entrada']) / pos['entrada']) * 100
                        resultado_str = "<b>WIN</b> 🎯" if pnl > 0 else "<b>LOSS</b> ❌"
                        cor_emoji = "🟢" if pnl > 0 else "🔴"

                        msg_resultado = (
                            f"{cor_emoji} <b>OPERAÇÃO ENCERRADA M1</b> | #{hashtag}\n\n"
                            f"📌 <b>Tipo:</b> LONG\n"
                            f"🏁 <b>Resultado:</b> {resultado_str} ({pnl:+.2f}%)\n"
                            f"📥 <b>Entrada:</b> ${pos['entrada']:.6f}\n"
                            f"📤 <b>Saída:</b> ${pos['ts_price']:.6f}"
                        )
                        enviar_telegram_simples(msg_resultado)
                        pos['ativa'] = False

                elif pos['tipo'] == 'SELL':
                    novo_ts = low_atual * (1 + (TS_PCT / 100))
                    pos['ts_price'] = min(pos['ts_price'], novo_ts)

                    if high_atual >= pos['ts_price']:
                        pnl = ((pos['entrada'] - pos['ts_price']) / pos['entrada']) * 100
                        resultado_str = "<b>WIN</b> 🎯" if pnl > 0 else "<b>LOSS</b> ❌"
                        cor_emoji = "🟢" if pnl > 0 else "🔴"

                        msg_resultado = (
                            f"{cor_emoji} <b>OPERAÇÃO ENCERRADA M1</b> | #{hashtag}\n\n"
                            f"📌 <b>Tipo:</b> SHORT\n"
                            f"🏁 <b>Resultado:</b> {resultado_str} ({pnl:+.2f}%)\n"
                            f"📥 <b>Entrada:</b> ${pos['entrada']:.6f}\n"
                            f"📤 <b>Saída:</b> ${pos['ts_price']:.6f}"
                        )
                        enviar_telegram_simples(msg_resultado)
                        pos['ativa'] = False

            # GERAÇÃO DE NOVOS SINAIS
            elif bot_rodando:
                cruzou_alta = (penultima['ema_fast'] <= penultima['ema_slow']) and (ultima_fechada['ema_fast'] > ultima_fechada['ema_slow'])
                cruzou_baixa = (penultima['ema_fast'] >= penultima['ema_slow']) and (ultima_fechada['ema_fast'] < ultima_fechada['ema_slow'])

                if cruzou_alta and ultima_fechada['rsi'] > 50:
                    pos['ativa'] = True
                    pos['tipo'] = 'BUY'
                    pos['entrada'] = preco_atual
                    pos['ts_price'] = preco_atual * (1 - (TS_PCT / 100))

                    msg_sinal = (
                        f"⚡ <b>SINAL M1 ULTRA SCALPER</b> | #{hashtag}\n\n"
                        f"📊 <b>Direção:</b> 🟢 <b>LONG (COMPRA)</b>\n"
                        f"💵 <b>Entrada:</b> ${preco_atual:.6f}\n"
                        f"🛡 <b>Trailing Stop:</b> ${pos['ts_price']:.6f} ({TS_PCT}%)\n\n"
                        f"🔥 <i>EMA 9x21 Cruzou para CIMA | RSI: {ultima_fechada['rsi']:.1f}</i>"
                    )
                    enviar_telegram_com_botao(msg_sinal, hashtag)

                elif cruzou_baixa and ultima_fechada['rsi'] < 50:
                    pos['ativa'] = True
                    pos['tipo'] = 'SELL'
                    pos['entrada'] = preco_atual
                    pos['ts_price'] = preco_atual * (1 + (TS_PCT / 100))

                    msg_sinal = (
                        f"⚡ <b>SINAL M1 ULTRA SCALPER</b> | #{hashtag}\n\n"
                        f"📊 <b>Direção:</b> 🔴 <b>SHORT (VENDA)</b>\n"
                        f"💵 <b>Entrada:</b> ${preco_atual:.6f}\n"
                        f"🛡 <b>Trailing Stop:</b> ${pos['ts_price']:.6f} ({TS_PCT}%)\n\n"
                        f"🔥 <i>EMA 9x21 Cruzou para BAIXO | RSI: {ultima_fechada['rsi']:.1f}</i>"
                    )
                    enviar_telegram_com_botao(msg_sinal, hashtag)

        except Exception as e:
            print(f"Erro em {symbol}: {e}")

        time.sleep(1.2)

print("==========================================")
print("BOT M1 INTERATIVO FULL INICIADO!")
print("==========================================")

enviar_telegram_simples("🤖 <b>BOT M1 SCALPER ONLINE COM PAINEL INTERATIVO!</b>\n\nEnvie /menu no chat para ver os comandos.")

while True:
    analisar_e_executar()
    time.sleep(10)
