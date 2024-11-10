from haystack import Pipeline
from haystack.components.builders.prompt_builder import PromptBuilder
from haystack.components.converters import TikaDocumentConverter
from haystack.components.preprocessors import DocumentCleaner
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.retrievers import InMemoryEmbeddingRetriever
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.document_stores.types import DuplicatePolicy
from haystack.components.writers import DocumentWriter

from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder
from haystack_integrations.components.embedders.ollama import OllamaTextEmbedder
from haystack_integrations.components.generators.ollama import OllamaGenerator

document_store = InMemoryDocumentStore(embedding_similarity_function='cosine')

pipeline = Pipeline()

pipeline.add_component('converter', TikaDocumentConverter())
pipeline.add_component('cleaner', DocumentCleaner())
pipeline.add_component('splitter', DocumentSplitter(split_by='sentence', split_length=5))
pipeline.add_component('embedder', OllamaDocumentEmbedder())
pipeline.add_component('writer', DocumentWriter(document_store=document_store, policy=DuplicatePolicy.OVERWRITE))

pipeline.connect('converter', 'cleaner')
pipeline.connect('cleaner', 'splitter')
pipeline.connect('splitter', 'embedder')
pipeline.connect('embedder', 'writer')

print(pipeline.run({'converter': {'sources': ['./test.pdf']}}))

pipeline = Pipeline()

template = """
Given the following documents, answer the question.

Context: 
{% for document in documents %}
    {{ document.content }}
{% endfor %}

Question: {{ query }}?
"""

pipeline.add_component('text_embedder', OllamaTextEmbedder())
pipeline.add_component('retriever', InMemoryEmbeddingRetriever(document_store=document_store))
pipeline.add_component('prompt_builder', PromptBuilder(template=template))
pipeline.add_component('llm', OllamaGenerator(model='llama3.2:3b'))

pipeline.connect('text_embedder.embedding', 'retriever.query_embedding')
pipeline.connect('retriever', 'prompt_builder.documents')
pipeline.connect('prompt_builder', 'llm')

query = 'Um número pode ter representação finita em uma base e não finita em outra base?'
print(pipeline.run({'prompt_builder': {'query': query}, 'text_embedder': {'text': query}}))