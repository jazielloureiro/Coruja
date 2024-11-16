CREATE TABLE chatbot (
	id INTEGER PRIMARY KEY,
	token VARCHAR(256) NOT NULL,
	name VARCHAR(128) NOT NULL,
	username VARCHAR(32) NOT NULL
);

CREATE TABLE resource (
	id INTEGER PRIMARY KEY,
	chatbot_id INTEGER NOT NULL REFERENCES chatbot (id),
	name VARCHAR(128) NOT NULL
);

CREATE TABLE resource_document (
	resource_id INTEGER NOT NULL REFERENCES resource (id),
	document_id VARCHAR(64) NOT NULL
);