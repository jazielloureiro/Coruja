CREATE TABLE chatbot (
	id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	token TEXT NOT NULL,
	name TEXT NOT NULL,
	username TEXT NOT NULL
);

CREATE TABLE resource (
	id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	chatbot_id INTEGER NOT NULL REFERENCES chatbot (id),
	name TEXT NOT NULL
);

CREATE TABLE resource_document (
	resource_id INTEGER NOT NULL REFERENCES resource (id),
	document_id TEXT NOT NULL
);