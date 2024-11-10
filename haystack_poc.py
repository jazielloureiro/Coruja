from haystack import Pipeline
from haystack.components.converters import TikaDocumentConverter
from haystack.components.preprocessors import DocumentCleaner
from haystack.components.preprocessors import DocumentSplitter

pipeline = Pipeline()

pipeline.add_component("converter", TikaDocumentConverter())
pipeline.add_component("cleaner", DocumentCleaner())
pipeline.add_component("splitter", DocumentSplitter(split_by="sentence", split_length=5))

pipeline.connect("converter", "cleaner")
pipeline.connect("cleaner", "splitter")

print(pipeline.run({"converter": {"sources": ['./test.pdf']}}))