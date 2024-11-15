import os
import queue
import re
import telebot
import threading
import time

from haystack import Pipeline
from haystack.components.builders.prompt_builder import PromptBuilder
from haystack.components.converters import TikaDocumentConverter
from haystack.components.fetchers import LinkContentFetcher
from haystack.components.preprocessors import DocumentCleaner
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from haystack.utils import Secret

from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack_integrations.components.generators.ollama import OllamaGenerator
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore

bot = telebot.TeleBot(os.getenv('TELEGRAM_TOKEN'))

connection_string = f'postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_URL')}/{os.getenv('POSTGRES_DB')}'

document_store = PgvectorDocumentStore(connection_string=Secret.from_token(connection_string))

@bot.message_handler(content_types=['document'])
def generate_embeddings(message):
    pipeline = Pipeline()

    pipeline.add_component('fetcher', LinkContentFetcher())
    pipeline.add_component('converter', TikaDocumentConverter(tika_url=os.getenv('TIKA_URL')))
    pipeline.add_component('cleaner', DocumentCleaner())
    pipeline.add_component('splitter', DocumentSplitter(split_by='sentence', split_length=5))
    pipeline.add_component('embedder', OllamaDocumentEmbedder(url=os.getenv('OLLAMA_URL')))
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

    pipeline = Pipeline()

    template = """
    Given the following documents, answer the question.

    Context: 
    {% for document in documents %}
        {{ document.content }}
    {% endfor %}

    Question: {{ query }}?
    """

    pipeline.add_component('text_embedder', OllamaTextEmbedder(url=os.getenv('OLLAMA_URL')))
    pipeline.add_component('retriever', PgvectorEmbeddingRetriever(document_store=document_store))
    pipeline.add_component('prompt_builder', PromptBuilder(template=template))
    pipeline.add_component('llm', OllamaGenerator(model='llama3.2:3b', url=os.getenv('OLLAMA_URL'), streaming_callback=lambda x: message_queue.put((x.content, False))))

    pipeline.connect('text_embedder.embedding', 'retriever.query_embedding')
    pipeline.connect('retriever', 'prompt_builder.documents')
    pipeline.connect('prompt_builder', 'llm')

    threading.Thread(target=send_message_stream_async, args=[message_queue, message.chat.id]).start()
    
    pipeline.run({'prompt_builder': {'query': message.text}, 'text_embedder': {'text': message.text}})

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