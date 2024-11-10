from haystack import Pipeline
from haystack.components.converters import TikaDocumentConverter
from haystack.components.preprocessors import DocumentCleaner
from haystack.components.preprocessors import DocumentSplitter
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.document_stores.types import DuplicatePolicy
from haystack.components.writers import DocumentWriter
from haystack_integrations.components.embedders.ollama import OllamaDocumentEmbedder

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