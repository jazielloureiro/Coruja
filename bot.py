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

from telebot import TeleBot, types, util
from telebot.handler_backends import BaseMiddleware
from telebot.custom_filters import AdvancedCustomFilter
from telebot.util import update_types

from transitions import Machine

from entities import ChatState, Chatbot, ResourceDocument, Resource

from services import ChatbotService

from repositories import ValkeyChatStateRepository, PostgresChatbotRepository, PostgresResourceDocumentRepository, PostgresResourceRepository

chat_state_repository = ValkeyChatStateRepository()
chatbot_repository = PostgresChatbotRepository()
resource_document_repository = PostgresResourceDocumentRepository()
resource_repository = PostgresResourceRepository()

class MainBotMachine(ChatState):
    def __init__(self, bot_username, chat_id):
        self.bot_username = bot_username
        self.chat_id = chat_id

        self._states = ['chatbot_menu', 'chatbot_ask_for_token', 'chatbot_registered', 'resource_menu', 'ask_for_resource']

        self._machine = Machine(model=self, states=self._states, initial='chatbot_menu', after_state_change='persist')
    
    def persist(self):
        chat_state_repository.save(self)

class StateMiddleware(BaseMiddleware):
    def __init__(self, bot: TeleBot):
        self.bot = bot
        self.update_types = update_types

    def pre_process(self, message: types.Message | types.CallbackQuery, data):
        if isinstance(message, types.CallbackQuery):
            chat_id = message.message.chat.id
        else:
            chat_id = message.chat.id

        state = chat_state_repository.find(self.bot.user.username, chat_id)

        if not state:
            state = MainBotMachine(self.bot.user.username, chat_id)
            state.persist()
        
        data['state'] = state

    def post_process(self, message, data, exception):
        pass

class StateFilter(AdvancedCustomFilter):
    key = 'state'

    def __init__(self, bot: TeleBot):
        self.bot = bot

    def check(self, message, text):
        if isinstance(message, types.CallbackQuery):
            chat_id = message.message.chat.id
        else:
            chat_id = message.chat.id

        state = chat_state_repository.find(self.bot.user.username, chat_id)

        if not state:
            state = MainBotMachine(self.bot.user.username, chat_id)
            state.persist()

        return state.state == text

bot = TeleBot(os.getenv('TELEGRAM_TOKEN'), use_class_middlewares=True)

bot.add_custom_filter(StateFilter(bot))

bot.setup_middleware(StateMiddleware(bot))

connection_string = f'postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_URL')}/{os.getenv('POSTGRES_DB')}'

@bot.message_handler(commands=['start', 'chatbots'])
def send_chatbots_menu(message: types.Message, state: MainBotMachine):
    state.to_chatbot_menu()

    chatbot_service = ChatbotService(chatbot_repository)
    chatbots = chatbot_service.list_chatbots()

    keyboard_data = {'\U0001F4BE Novo': {'callback_data': 'new_chatbot'}}

    for i in chatbots:
        keyboard_data[f'\U0001F916 {i.name}'] = {'callback_data': f'{i.id}_{i.name}_{i.username}'}

    inline_keyboard = util.quick_markup(keyboard_data, row_width=1)

    bot.send_message(message.chat.id, 'Chatbots', reply_markup=inline_keyboard)

@bot.callback_query_handler(state='chatbot_menu', func=lambda x: x.data == 'new_chatbot')
def ask_for_new_chatbot_token(callback_query: types.CallbackQuery, state: MainBotMachine):
    state.to_chatbot_ask_for_token()

    bot.send_message(callback_query.message.chat.id, 'Token?')

@bot.message_handler(state='chatbot_ask_for_token', content_types=['text'])
def register_chatbot(message: types.Message, state: MainBotMachine):
    child_bot = TeleBot(message.text)

    bot_information = child_bot.get_me()

    chatbot_repository.save(Chatbot(token=message.text, name=bot_information.first_name, username=bot_information.username))

    child_bot.register_message_handler(ask_model, content_types=['text'], pass_bot=True)

    threading.Thread(target=child_bot.infinity_polling).start()

    state.to_chatbot_registered()

@bot.callback_query_handler(state='chatbot_menu')
def send_resources_menu(callback_query: types.CallbackQuery, state: MainBotMachine):
    state.to_resource_menu()

    chatbot_id, chatbot_name, chatbot_username = callback_query.data.split('_')

    state.child_bot_id = chatbot_id
    state.child_bot_username = chatbot_username
    state.persist()

    keyboard_data = {'\U0001F4BE Novo': { 'callback_data': 'new_resource' }}

    resources = resource_repository.find(chatbot_id)

    for i in resources:
        keyboard_data[f'\U0001F4DA {i.name}'] = { 'callback_data': f'resource_{i.id}' }

    inline_keyboard = util.quick_markup(keyboard_data, row_width=1)

    bot.send_message(callback_query.message.chat.id, chatbot_name, reply_markup=inline_keyboard)

@bot.callback_query_handler(state='resource_menu', func=lambda x: x.data == 'new_resource')
def ask_for_new_resource(callback_query: types.CallbackQuery, state: MainBotMachine):
    state.to_ask_for_resource()

    bot.send_message(callback_query.message.chat.id, 'Resource?')

@bot.message_handler(state='ask_for_resource', content_types=['document'])
def generate_embeddings(message: types.Message, state: MainBotMachine):
    pipeline = Pipeline()

    document_store = PgvectorDocumentStore(connection_string=Secret.from_token(connection_string), table_name=f'document_{state.child_bot_username}', keyword_index_name=f'{state.child_bot_username}_index')

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

    documents = pipeline.run({'fetcher': {'urls': [bot.get_file_url(message.document.file_id)]}}, include_outputs_from=set(['splitter']))

    resource_id = resource_repository.save(Resource(chatbot_id=state.child_bot_id, name=message.document.file_name))

    resource_document_repository.save_many([ResourceDocument(resource_id, i.id) for i in documents['splitter']['documents']])

    bot.send_message(message.chat.id, 'Arquivo processado!')

def ask_model(message: types.Message, bot: TeleBot):
    message_queue = queue.Queue()

    pipeline = Pipeline()

    bot_information = bot.get_me()

    document_store = PgvectorDocumentStore(connection_string=Secret.from_token(connection_string), table_name=f'document_{bot_information.username}', keyword_index_name=f'{bot_information.username}_index')

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
    pipeline.add_component('llm', OllamaGenerator(model='llama3.2:3b', url=os.getenv('OLLAMA_URL'), raw=True, keep_alive=-1, streaming_callback=lambda x: message_queue.put((x.content, False))))

    pipeline.connect('text_embedder.embedding', 'retriever.query_embedding')
    pipeline.connect('retriever', 'prompt_builder.documents')
    pipeline.connect('prompt_builder', 'llm')

    threading.Thread(target=send_message_stream_async, args=[message_queue, bot, message.chat.id]).start()
    
    pipeline.run({'prompt_builder': {'query': message.text}, 'text_embedder': {'text': message.text}})

    message_queue.put(('', True))

def send_message_stream_async(message_queue, bot, chat_id, message_id = None, message_text = ''):
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