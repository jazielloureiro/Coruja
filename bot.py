import os
import queue
import re
import telebot
import threading
import time

from haystack_integrations.components.generators.ollama import OllamaGenerator

bot = telebot.TeleBot(os.getenv('TELEGRAM_TOKEN'))

@bot.message_handler(content_types=['text'])
def ask_model(message):
    message_queue = queue.Queue()

    generator = OllamaGenerator(model='llama3.2:3b', streaming_callback=lambda x: message_queue.put((x.content, False)))

    threading.Thread(target=send_message_stream_async, args=[message_queue, message.chat.id]).start()
    
    generator.run(message.text)

    message_queue.put(('', True))

def send_message_stream_async(message_queue, chat_id, message_id = None, message_text = ''):
    stream_end = False

    while not stream_end:
        need_send = False

        while message_queue.qsize() != 0:
            text, stream_end = message_queue.get_nowait()
            message_text += text
            need_send = True

        if need_send:
            message_end = '... \U0001F504'
            parse_mode = None

            if stream_end:
                message_end = ''
                parse_mode = 'MarkdownV2'
                message_text = re.sub(r'([\[\]\-_*()~>#+=|{}.!])', r'\\\1', message_text)

            if message_id:
                bot.edit_message_text(message_text + message_end, chat_id=chat_id, message_id=message_id, parse_mode=parse_mode)
            else:
                message_id = bot.send_message(chat_id, message_text + message_end, parse_mode=parse_mode).id
        
            time.sleep(1)

bot.infinity_polling()