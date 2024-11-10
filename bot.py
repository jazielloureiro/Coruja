import os
import queue
import re
import telebot
import threading
import time

from haystack import Pipeline
from haystack.components.converters import TikaDocumentConverter
from haystack.components.fetchers import LinkContentFetcher
from haystack.components.preprocessors import DocumentCleaner
from haystack.components.preprocessors import DocumentSplitter
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.document_stores.types import DuplicatePolicy
from haystack.components.writers import DocumentWriter

from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack_integrations.components.generators.ollama import OllamaGenerator

bot = telebot.TeleBot(os.getenv('TELEGRAM_TOKEN'))

@bot.message_handler(content_types=['document'])
def generate_embeddings(message):
    document_store = InMemoryDocumentStore(embedding_similarity_function='cosine')

    pipeline = Pipeline()

    pipeline.add_component('fetcher', LinkContentFetcher())
    pipeline.add_component('converter', TikaDocumentConverter())
    pipeline.add_component('cleaner', DocumentCleaner())
    pipeline.add_component('splitter', DocumentSplitter(split_by='sentence', split_length=5))
    pipeline.add_component('embedder', OllamaDocumentEmbedder())
    pipeline.add_component('writer', DocumentWriter(document_store=document_store, policy=DuplicatePolicy.OVERWRITE))

    pipeline.connect('fetcher.streams', 'converter.sources')
    pipeline.connect('converter', 'cleaner')
    pipeline.connect('cleaner', 'splitter')
    pipeline.connect('splitter', 'embedder')
    pipeline.connect('embedder', 'writer')

    pipeline.run({'fetcher': {'urls': [bot.get_file_url(message.document.file_id)]}})

    bot.send_message(message.chat.id, 'Arquivo processado!')

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