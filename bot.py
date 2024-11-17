import os
import queue
import re
import threading
import time

from haystack import Pipeline
from haystack.components.builders.prompt_builder import PromptBuilder
from haystack.components.converters import TikaDocumentConverter
from haystack.components.fetchers import LinkContentFetcher
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy
from haystack.utils import Secret

from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder, OllamaTextEmbedder
from haystack_integrations.components.generators.ollama import OllamaGenerator
from haystack_integrations.components.retrievers.pgvector import PgvectorEmbeddingRetriever
from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore

import psycopg

from telebot import custom_filters, TeleBot, types, util
from telebot.states import State, StatesGroup
from telebot.states.sync.context import StateContext
from telebot.states.sync.middleware import StateMiddleware
from telebot.storage import StateMemoryStorage

state_storage = StateMemoryStorage()

bot = TeleBot(os.getenv('TELEGRAM_TOKEN'), state_storage=state_storage, use_class_middlewares=True)

bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.setup_middleware(StateMiddleware(bot))

connection_string = f'postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_URL')}/{os.getenv('POSTGRES_DB')}'

document_store = PgvectorDocumentStore(connection_string=Secret.from_token(connection_string))

class States(StatesGroup):
    chatbot_menu = State()
    chatbot_register = State()

@bot.message_handler(commands=['start', 'chatbots'])
def send_chatbots_menu(message: types.Message, state: StateContext):
    state.set(States.chatbot_menu)

    inline_keyboard = util.quick_markup({
        '\U0001F4BE Novo': { 'callback_data': 'new_chatbot' },
        '\U0001F916 Chatbot': { 'callback_data': 'cb1' },
    }, row_width=1)

    bot.send_message(message.chat.id, 'Chatbots', reply_markup=inline_keyboard)

@bot.callback_query_handler(state=States.chatbot_menu, func=lambda x: x.data == 'new_chatbot')
def handle_chatbots_menu_action(callback_query: types.CallbackQuery, state: StateContext):
    state.set(States.chatbot_register)

    bot.send_message(callback_query.message.chat.id, 'Token?')

@bot.message_handler(state=States.chatbot_register, content_types=['text'])
def register_chatbot(message: types.Message, state: StateContext):
    client_bot = TeleBot(message.text)

    bot_information = client_bot.get_me()

    with psycopg.connect(connection_string) as connection:
        with connection.cursor() as cursor:
            cursor.execute('INSERT INTO chatbot (token, name, username) VALUES (%s, %s, %s)', (message.text, bot_information.first_name, bot_information.username))
            
            connection.commit()
    
    client_bot.send_message(message.from_user.id, 'Hey')

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